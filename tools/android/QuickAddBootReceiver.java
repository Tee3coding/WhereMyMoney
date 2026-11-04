package com.wheremymoney.quickadd;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Puts the quick-add notification back after the phone restarts. */
public class QuickAddBootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            QuickAddHelper.sync(context, true);
        }
    }
}