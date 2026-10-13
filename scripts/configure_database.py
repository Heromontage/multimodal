"""Create local Docker database credentials without overwriting existing values."""
from pathlib import Path
import secrets

path = Path(__file__).resolve().parents[1] / '.env'
existing = path.read_text() if path.exists() else ''
keys = {line.split('=', 1)[0] for line in existing.splitlines() if '=' in line}
missing = [name for name in ('MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD') if name not in keys]
if missing:
    path.write_text(existing.rstrip() + '\n' +
                    '\n'.join(name + '=' + secrets.token_hex(32) for name in missing) + '\n')
    path.chmod(0o600)
print('Database credentials are configured in .env.')
