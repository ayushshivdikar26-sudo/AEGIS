"""AEGIS Backend Root Package."""

import re
import contextlib

# Patch supabase client to support new Supabase key formats (sb_publishable_..., sb_secret_...)
with contextlib.suppress(Exception):
    from supabase._sync import client as sync_client
    from supabase._async import client as async_client

    for client_class in (sync_client.SyncClient, async_client.AsyncClient):
        _orig_init = client_class.__init__

        def _make_init(orig_fn):
            def _patched_init(self, supabase_url: str, supabase_key: str, options=None):
                real_match = re.match
                try:
                    re.match = lambda pattern, string, *args, **kwargs: (
                        True
                        if isinstance(string, str) and string.startswith("sb_")
                        else real_match(pattern, string, *args, **kwargs)
                    )
                    orig_fn(self, supabase_url, supabase_key, options)
                finally:
                    re.match = real_match

            return _patched_init

        client_class.__init__ = _make_init(_orig_init)
