=====
Release History
=====

* **Release v0.0.9 (2025-03-20)**

  - Declare 'cryptography' dependency in optional extra ``[crypto]``

    - For now, it is still always required. This change simplifies dependency management downstream for Electrum.

* **Release v0.0.8 (2025-03-19)**

  - Use correct public key type in ``verify()`` method
  - Always verify signatures of queried events (**Previous versions don't automatically verify signatures!**)
  - Add tests for signature verification
  - Switch from ``websockets`` to ``aiohttp`` library for websocket connections
  - Add support for proxy connections
  - Bump min required Python version to 3.10
  - Add method to dynamically change relay list on existing RelayManager
  - Use platform independent ``os.urandom`` instead of ``getrandom`` for tests
