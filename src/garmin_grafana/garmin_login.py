"""One-time interactive Garmin Connect login (garmin-surreal helper).

Same login as garmin_fetch.garmin_login(), but the password is not echoed,
no database is needed, and it stops once the session tokens are saved in
TOKEN_DIR. Run it once per machine, then start the fetcher.

    python garmin_grafana/garmin_login.py
"""

import getpass
import os

from garminconnect import Garmin

token_dir = os.path.expanduser(os.getenv("TOKEN_DIR", "~/.garminconnect"))
if os.path.isfile(token_dir) and not token_dir.endswith('.json'):
    token_dir += "_tokens"  # same legacy-file mapping as garmin_fetch.garmin_login()
is_cn = os.getenv("GARMINCONNECT_IS_CN") in ['True', 'true', 'TRUE', 't', 'T', 'yes', 'Yes', 'YES', '1']

os.makedirs(token_dir, exist_ok=True)
email = (os.getenv("GARMINCONNECT_EMAIL") or "").strip() or input("Garmin Connect e-mail: ").strip()
password = getpass.getpass("Garmin Connect password (hidden): ")
garmin = Garmin(email=email, password=password, is_cn=is_cn,
                prompt_mfa=lambda: input("MFA one-time code (via email or SMS): ").strip())
garmin.login(token_dir)

saved = [name for name in os.listdir(token_dir) if not name.startswith(".")]
if not saved:
    raise SystemExit(f"Login worked but no tokens were written to {token_dir} — check folder permissions")
print(f"Login OK ({garmin.full_name or garmin.display_name}). Tokens saved in {token_dir}: {', '.join(saved)}")
