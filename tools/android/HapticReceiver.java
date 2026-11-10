package com.wheremymoney.quickadd;

import android.content.Context;
import android.os.Build;
import android.os.VibrationEffect;
import android.os.Vibrator;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;

/**
 * Vibrates the phone's motor directly when the Python app asks for a tap buzz.
 * Flutter's own haptic feedback follows the phone's "touch feedback" setting, which many phones leave off,
 * so the Python side sends one byte to 127.0.0.1:PORT instead: l (light), s (select), m (medium), h (heavy).
 * Needs the VIBRATE permission (added by patch_android.py).
 */
public final class HapticReceiver {
    static final int PORT = 47831;

    private static Thread thread;
    private static Vibrator vibrator;

    private HapticReceiver() {
    }

    public static synchronized void start(Context context) {
        if (thread != null) {
            return;
        }
        vibrator = (Vibrator) context.getApplicationContext().getSystemService(Context.VIBRATOR_SERVICE);
        thread = new Thread(new Runnable() {
            @Override
            public void run() {
                listen();
            }
        }, "haptic-receiver");
        thread.setDaemon(true);
        thread.start();
    }

    private static void listen() {
        try (DatagramSocket socket = new DatagramSocket(PORT, InetAddress.getByName("127.0.0.1"))) {
            byte[] buffer = new byte[8];
            DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
            while (true) {
                socket.receive(packet);
                if (packet.getLength() > 0) {
                    buzz((char) buffer[0]);
                }
            }
        } catch (Exception e) {
            synchronized (HapticReceiver.class) {
                thread = null;  // could not listen (port busy?): the Python side falls back to Flutter's haptics
            }
        }
    }

    private static void buzz(char kind) {
        if (vibrator == null || !vibrator.hasVibrator()) {
            return;
        }
        long millis = kind == 'h' ? 45 : kind == 'm' ? 25 : kind == 's' ? 12 : 15;
        int amplitude = kind == 'h' ? 255 : kind == 'm' ? 170 : 100;
        try {
            if (Build.VERSION.SDK_INT >= 26) {
                int strength = vibrator.hasAmplitudeControl() ? amplitude : VibrationEffect.DEFAULT_AMPLITUDE;
                vibrator.vibrate(VibrationEffect.createOneShot(millis, strength));
            } else {
                vibrator.vibrate(millis);
            }
        } catch (Exception ignored) {
            // a missing permission or motor must never crash the app
        }
    }
}
