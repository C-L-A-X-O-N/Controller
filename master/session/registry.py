sessions = set()

def add_session(session):
    global sessions
    if session not in sessions:
        sessions.add(session)
        return True
    return False

def remove_session(session):
    global sessions
    if session in sessions:
        sessions.remove(session)
        return True
    return False

def get_sessions():
    global sessions
    return sessions