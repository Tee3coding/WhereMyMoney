package com.wheremymoney.quickadd;

import android.Manifest;
import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/**
 * Shows the quiet "quick add" notification and finds the files the Python app shares with the pop-up form.
 * The Python side writes quick_config.json (what to show) and reads quick_inbox.jsonl (records typed in the form).
 */
public final class QuickAddHelper {
    static final String CONFIG_NAME = "quick_config.json";
    static final String INBOX_NAME = "quick_inbox.jsonl";
    static final String CHANNEL_ID = "quick_add_native";
    static final int NOTIFICATION_ID = 4242;

    private static final Handler HANDLER = new Handler(Looper.getMainLooper());
    private static File cachedConfig;
    private static Runnable poller;
    private static Boolean lastEnabled;
    private static boolean askedPermission;

    private QuickAddHelper() {
    }

    /** Python saves quick_config.json somewhere inside the app's data folder; find it once and remember. */
    static File findConfig(Context context) {
        if (cachedConfig != null && cachedConfig.exists()) {
            return cachedConfig;
        }
        File root = Build.VERSION.SDK_INT >= 24 ? context.getDataDir() : context.getFilesDir().getParentFile();
        cachedConfig = search(root, 0);
        return cachedConfig;
    }

    private static File search(File dir, int depth) {
        if (dir == null || depth > 7) {
            return null;
        }
        File[] children = dir.listFiles();
        if (children == null) {
            return null;
        }
        for (File child : children) {
            if (child.isFile() && child.getName().equals(CONFIG_NAME)) {
                return child;
            }
        }
        for (File child : children) {
            String name = child.getName();
            if (child.isDirectory() && !name.equals("cache") && !name.equals("code_cache")) {
                File hit = search(child, depth + 1);
                if (hit != null) {
                    return hit;
                }
            }
        }
        return null;
    }

    static JSONObject readConfig(Context context) {
        File file = findConfig(context);
        if (file == null) {
            return null;
        }
        try (InputStream in = new FileInputStream(file)) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            int read;
            while ((read = in.read(buffer)) > 0) {
                out.write(buffer, 0, read);
            }
            return new JSONObject(new String(out.toByteArray(), StandardCharsets.UTF_8));
        } catch (Exception e) {
            return null;
        }
    }

    /** force = post again even if nothing changed (app opened, phone restarted). */
    public static void sync(Context context, boolean force) {
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) {
            return;
        }
        JSONObject config = readConfig(context);
        boolean enabled = config != null && config.optBoolean("enabled", false);
        if (!force && lastEnabled != null && lastEnabled == enabled) {
            return;
        }
        lastEnabled = enabled;
        if (enabled && canNotify(context)) {
            post(context, manager, config);
        } else {
            manager.cancel(NOTIFICATION_ID);
        }
    }

    private static boolean canNotify(Context context) {
        if (Build.VERSION.SDK_INT < 33) {
            return true;
        }
        if (context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) {
            return true;
        }
        if (context instanceof Activity && !askedPermission) {
            askedPermission = true;
            ((Activity) context).requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, NOTIFICATION_ID);
        }
        return false;
    }

    private static void post(Context context, NotificationManager manager, JSONObject config) {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(CHANNEL_ID, "Quick add", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("A shortcut for adding records");
            channel.setShowBadge(false);
            manager.createNotificationChannel(channel);
        }
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(context, CHANNEL_ID)
                : new Notification.Builder(context);
        builder.setSmallIcon(android.R.drawable.ic_input_add)
                .setContentTitle(config.optString("app", "WhereMyMoney"))
                .setContentText("Tap to add a record")
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setShowWhen(false)
                .setContentIntent(formIntent(context, "expense", 1));
        builder.addAction(0, "Expense", formIntent(context, "expense", 2));
        builder.addAction(0, "Income", formIntent(context, "income", 3));
        builder.addAction(0, "Open app", openAppIntent(context));
        if (Build.VERSION.SDK_INT < 26) {
            builder.setPriority(Notification.PRIORITY_LOW);
        }
        manager.notify(NOTIFICATION_ID, builder.build());
    }

    private static int flags() {
        return PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0);
    }

    private static PendingIntent formIntent(Context context, String kind, int requestCode) {
        Intent intent = new Intent(context, QuickAddActivity.class);
        intent.putExtra("kind", kind);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        return PendingIntent.getActivity(context, requestCode, intent, flags());
    }

    private static PendingIntent openAppIntent(Context context) {
        Intent intent = context.getPackageManager().getLaunchIntentForPackage(context.getPackageName());
        if (intent == null) {
            intent = new Intent();
        }
        return PendingIntent.getActivity(context, 4, intent, flags());
    }

    /** Called by MainActivity when the app comes to the front: re-post, then watch for the switch in Settings. */
    public static void onResume(final Activity activity) {
        stop();
        BiometricHelper.onResume(activity);
        sync(activity, true);
        poller = new Runnable() {
            @Override
            public void run() {
                sync(activity, false);
                HANDLER.postDelayed(this, 2000);
            }
        };
        HANDLER.postDelayed(poller, 2000);
    }

    public static void onPause() {
        stop();
        BiometricHelper.onPause();
    }

    private static void stop() {
        if (poller != null) {
            HANDLER.removeCallbacks(poller);
            poller = null;
        }
    }
}