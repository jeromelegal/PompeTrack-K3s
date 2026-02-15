from __future__ import annotations

import os
import sys
import time
import stat
from pathlib import Path
from typing import Optional


class SecretReadError(RuntimeError):
    """Erreur de lecture de secret (fichier manquant, vide, permissions, etc.)."""


def read_secret_from_file(
    env_var_name: str,
    fallback_env: Optional[str],
    *,
    required: bool = True,
    wait_seconds: float = 0.0,
    warn_on_perms: bool = True,
    min_length: int = 1,
    strip: bool = True,
    encoding: str = "utf-8",
) -> str:
    """
    Lit un secret depuis un chemin contenu dans la variable d'env `env_var_name`.
    - Si `env_var_name` est absent ou vide, tente la variable d'env `fallback_env`.
    - Si rien n'est disponible et `required=True`, lève SecretReadError (sinon renvoie "").
    - Optionnellement attend jusqu'à `wait_seconds` l'apparition du fichier secret.
    - Emet un avertissement si les permissions du fichier ne sont pas restrictives.
    - Vérifie que la longueur minimale est respectée.

    Retourne la valeur du secret (str).

    Exemples :
        redis_password = read_secret_from_file("REDIS_PASSWORD_FILE", "REDIS_PASSWORD")
    """
    file_path = os.getenv(env_var_name, "") or ""

    # 1) Lecture via fichier si fourni
    if file_path:
        p = Path(file_path)

        # Attente optionnelle si le fichier n'existe pas encore (montage tardif)
        if wait_seconds > 0 and not p.exists():
            deadline = time.time() + wait_seconds
            while time.time() < deadline and not p.exists():
                time.sleep(0.1)

        if not p.exists():
            msg = f"Secret file '{file_path}' does not exist"
            if required and fallback_env is None:
                raise SecretReadError(msg)
            # Sinon: on tentera fallback env var
        else:
            # Vérif permissions (non bloquant)
            if warn_on_perms:
                try:
                    mode = stat.S_IMODE(p.stat().st_mode)
                    if mode & 0o077:  # groupe/others ont des droits
                        print(
                            f"[WARN] permissions for {file_path} are not restrictive "
                            f"(mode {oct(mode)}). Consider chmod 600 or 400.",
                            file=sys.stderr,
                        )
                except Exception:
                    # On ne bloque pas si stat() échoue (FS exotique)
                    pass

            try:
                data = p.read_text(encoding=encoding)
            except Exception as e:
                raise SecretReadError(f"Cannot read secret file '{file_path}': {e}") from e

            if strip:
                data = data.strip("\r\n\t ")

            if len(data) < min_length:
                raise SecretReadError(
                    f"Secret in '{file_path}' is too short (len={len(data)} < {min_length})"
                )

            return data

    # 2) Fallback sur variable d'environnement
    if fallback_env:
        val = os.getenv(fallback_env, "")
        if strip:
            val = val.strip("\r\n\t ")
        if val:
            if len(val) < min_length:
                raise SecretReadError(
                    f"Env var {fallback_env} value is too short (len={len(val)} < {min_length})"
                )
            return val

    # 3) Rien trouvé
    if required:
        sources = [env_var_name] + ([fallback_env] if fallback_env else [])
        raise SecretReadError(
            f"No secret provided via {', '.join([s for s in sources if s])}"
        )

    return ""
