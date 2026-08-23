/*
 * AzureBranches EXP: AzureProxy mode presets (SAFE / ACCESS / EXP).
 *
 * Companion to AzureBranches' command_blocks.mode concept: one proxy-side
 * switch that re-tunes the Velocity network/command surface for the target
 * backend family.
 *
 *  - SAFE   : strict upstream behaviour, no changes (default).
 *  - ACCESS : operational observability - command execution logging.
 *  - EXP    : AzureBranches EXP7 pairing - observability plus a tidy command
 *             surface (no proxy command tree injected into the backend) and
 *             MODERN forwarding enforced (secret validated by the existing
 *             upstream sanity check).
 *
 * Fails soft: unknown mode strings fall back to SAFE with a warning.
 */
package com.azureproxy.config;

import com.electronwill.nightconfig.core.CommentedConfig;

public final class AzureProxyMode {

    public enum Mode {
        SAFE,
        ACCESS,
        EXP
    }

    private AzureProxyMode() {
    }

    /** Applies the {azureproxy.mode} preset onto the raw nightconfig before Velocity's own field binding. */
    public static void applyToConfig(final CommentedConfig root, final CommentedConfig advanced) {
        final Object raw = root.get("azureproxy.mode");
        final String value = raw == null ? "SAFE" : String.valueOf(raw).trim();
        final Mode mode;
        try {
            mode = Mode.valueOf(value.toUpperCase(java.util.Locale.ROOT));
        } catch (final IllegalArgumentException e) {
            System.out.println("[AzureProxy] Unknown azureproxy.mode '" + value + "', keeping SAFE");
            return;
        }

        if (mode == Mode.SAFE) {
            System.out.println("[AzureProxy] azureproxy.mode=SAFE (upstream defaults)");
            return;
        }

        // ACCESS and EXP share the observability preset
        advanced.set("log-command-executions", true);

        if (mode == Mode.EXP) {
            // keep the proxy command tree out of the backend's client command surface
            advanced.set("announce-proxy-commands", false);
            // EXP7 pairing: modern forwarding with the backend-side velocity-support
            if (root.get("player-info-forwarding-mode") == null) {
                root.set("player-info-forwarding-mode", "MODERN");
                System.out.println("[AzureProxy] azureproxy.mode=EXP: forced player-info-forwarding-mode=MODERN");
            }
            // NOTE: announce-proxy-commands stays at its upstream default (true) so the
            // client command tree keeps /server tab-completion (an override broke it).
            System.out.println(
                "[AzureProxy] azureproxy.mode=EXP applied (log-command-executions=true)");
        } else {
            System.out.println("[AzureProxy] azureproxy.mode=ACCESS applied (log-command-executions=true)");
        }
    }
}
