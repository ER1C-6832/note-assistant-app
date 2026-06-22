"""
Controllers — bridge between QML UI and Python backend services.

Each controller manages a specific domain:
- notes_controller: CRUD operations via Notes API
- assistant_controller: voice assistant state via Sidecar WebSocket
- app_state: global application state shared with QML
"""
