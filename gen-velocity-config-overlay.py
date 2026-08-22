# -*- coding: utf-8 -*-
"""Generate azurepatches-src overlay for VelocityConfiguration.java:
insert the AzureProxyMode preset application right after the packetLimiter
binding (before the forwarding-secret sanity check so a MODERN forced by the
EXP preset is validated by the upstream check)."""
import subprocess
from pathlib import Path

REL = 'proxy/src/main/java/com/velocitypowered/proxy/config/VelocityConfiguration.java'
SRC = subprocess.run(
    ['git', '-C', r'F:\AzureCore\AzureProxy\build\velocity-src', 'show', 'HEAD:' + REL],
    capture_output=True, text=True, check=True).stdout

ANCHOR = '      final PacketLimiterConfig packetLimiterConfig = PacketLimiterConfig.fromConfig(config.get("packet-limiter"));'
INSERT = (
    ANCHOR +
    '\n\n'
    '      // AzureBranches EXP: azureproxy.mode presets (SAFE/ACCESS/EXP) - tune the raw\n'
    '      // nightconfig before upstream field binding so presets flow through the normal\n'
    '      // constructors and migrations/validations (e.g. MODERN forwarding secret check).\n'
    '      com.azureproxy.config.AzureProxyMode.applyToConfig(config, advancedConfig);'
)
assert SRC.count(ANCHOR) == 1, 'anchor count=%d' % SRC.count(ANCHOR)
patched = SRC.replace(ANCHOR, INSERT)

DST = Path(r'F:\AzureCore\AzureProxy\azurepatches-src') / REL
DST.parent.mkdir(parents=True, exist_ok=True)
DST.write_text(patched, encoding='utf-8')
print('wrote', DST, len(patched), 'bytes; insert ok')
