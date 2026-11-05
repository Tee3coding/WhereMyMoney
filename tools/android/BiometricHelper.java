package com.wheremymoney.quickadd;

import android.annotation.TargetApi;
import android.app.Activity;
import android.content.DialogInterface;
import android.content.pm.PackageManager;
import android.hardware.biometrics.BiometricManager;
import android.hardware.biometrics.BiometricPrompt;
import android.os.Build;
import android.os.CancellationSignal;
import android.os.Handler;
import android.os.Looper;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.Executor;

/**
 * Fingerprint unlock for the app lock, using Android's own system prompt (no extra libraries; Android 9+).
 * The Python app and this class talk through small files in the app's private data folder:
 *   biometric_request.txt  Python writes a random token here when the lock screen wants a fingerprint.
 *   biometric_result.txt   after a successful fingerprint this class writes the same token back.
 *   biometric_status.txt   "yes" or "no": can this phone do fingerprint unlock right now?
 * Only this app can write into that folder, and Python checks the token, so nothing else can fake a success.
 */
public final class BiometricHelper {
    static final String REQUEST = "biometric_request.txt";
    static final String RESULT = "biometric_result.txt";
    static final String STATUS = "biometric_status.txt";

    private static final Handler HANDLER = new Handler(Looper.getMainLooper());
    private static Runnable poller;
    private static boolean prompting;
    private static long finishedAt;  // when the last prompt ended; requests right after it are duplicates

    private BiometricHelper() {
    }

    /** Called from QuickAddHelper.onResume: report whether fingerprint works, then watch for requests. */
    public static void onResume(final Activity activity) {
        onPause();
        writeStatus(activity);
        poller = new Runnable() {
            @Override
            public void run() {
                check(activity);
                HANDLER.postDelayed(this, 400);
            }
        };
        HANDLER.post(poller);
    }

    public static void onPause() {
        if (poller != null) {
            HANDLER.removeCallbacks(poller);
            poller = null;
        }
    }

    private static File folder(Activity activity) {
        File config = QuickAddHelper.findConfig(activity);
        return config == null ? null : config.getParentFile();
    }

    private static boolean available(Activity activity) {
        try {
            if (Build.VERSION.SDK_INT >= 30) {
                BiometricManager manager = activity.getSystemService(BiometricManager.class);
                return manager != null
                        && manager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG)
                        == BiometricManager.BIOMETRIC_SUCCESS;
            }
            if (Build.VERSION.SDK_INT >= 29) {
                BiometricManager manager = activity.getSystemService(BiometricManager.class);
                return manager != null && manager.canAuthenticate() == BiometricManager.BIOMETRIC_SUCCESS;
            }
            return Build.VERSION.SDK_INT == 28
                    && activity.getPackageManager().hasSystemFeature(PackageManager.FEATURE_FINGERPRINT);
        } catch (Exception e) {
            return false;
        }
    }

    private static void writeStatus(Activity activity) {
        File dir = folder(activity);
        if (dir != null) {
            write(new File(dir, STATUS), available(activity) ? "yes" : "no");
        }
    }

    private static void check(Activity activity) {
        if (prompting || Build.VERSION.SDK_INT < 28) {
            return;
        }
        File dir = folder(activity);
        if (dir == null) {
            return;
        }
        File request = new File(dir, REQUEST);
        if (!request.exists()) {
            return;
        }
        String token = read(request);
        request.delete();
        if (System.currentTimeMillis() - finishedAt < 1500) {
            return;  // a request that arrives right after a prompt closed is a duplicate; the PIN screen still works
        }
        if (token.isEmpty() || !available(activity)) {
            return;
        }
        show(activity, dir, token);
    }

    @TargetApi(28)
    private static void show(Activity activity, final File dir, final String token) {
        prompting = true;
        try {
            Executor executor = activity.getMainExecutor();
            BiometricPrompt prompt = new BiometricPrompt.Builder(activity)
                    .setTitle("Unlock")
                    .setSubtitle("Use your fingerprint")
                    .setNegativeButton("Use PIN", executor, new DialogInterface.OnClickListener() {
                        @Override
                        public void onClick(DialogInterface dialog, int which) {
                            finish();
                        }
                    })
                    .build();
            prompt.authenticate(new CancellationSignal(), executor, new BiometricPrompt.AuthenticationCallback() {
                @Override
                public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult result) {
                    finish();
                    write(new File(dir, RESULT), token);
                }

                @Override
                public void onAuthenticationError(int errorCode, CharSequence errString) {
                    finish();
                }
            });
        } catch (Exception e) {
            finish();
        }
    }

    private static void finish() {
        prompting = false;
        finishedAt = System.currentTimeMillis();
    }

    private static String read(File file) {
        try (InputStream in = new FileInputStream(file)) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buffer = new byte[256];
            int count;
            while ((count = in.read(buffer)) > 0) {
                out.write(buffer, 0, count);
            }
            return new String(out.toByteArray(), StandardCharsets.UTF_8).trim();
        } catch (Exception e) {
            return "";
        }
    }

    private static void write(File file, String text) {
        File temp = new File(file.getPath() + ".tmp");
        try (FileOutputStream out = new FileOutputStream(temp)) {
            out.write(text.getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) {
            return;
        }
        temp.renameTo(file);
    }
}
