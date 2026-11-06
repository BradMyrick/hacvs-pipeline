"""hacvsp ui — local-first web dashboard (operator cockpit).

stdlib-only: ThreadingHTTPServer + server-rendered HTML + one vendored CSS.
Binds 127.0.0.1 by default. Writes go to the same files the pipeline reads;
signing shells out to ssh-keygen/cosign on the host — keys never render.
"""
