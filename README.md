# Kerbl Smart Energizer for Home Assistant

Unofficial Home Assistant integration for AKO / Kerbl **smart electric fence energizers**
(for example Duo Power Xi8000 Smart) through the Kerbl Welt cloud, the same account as the
Kerbl Welt app.

Status: **0.1, read-only and generic.** Kerbl does not document what an energizer reports,
so this version makes a sensor for every numeric field and a binary sensor for every
true/false field it finds. Diagnostics (Download diagnostics on the integration) contain the
full redacted device response, used to build proper entities and on/off control later.

## Install

Marketplace (HACS) → Custom repositories → `Wilsson2000/ha-kerbl-energizer`, type
Integration → install → Settings → Devices & services → Add integration →
**Kerbl Smart Energizer**, and sign in with your Kerbl Welt e-mail and password.

API endpoints and token refresh follow [stgarrity/kerblwelt-api](https://github.com/stgarrity/kerblwelt-api) (MIT).
Not affiliated with Albert Kerbl GmbH or AKO.
