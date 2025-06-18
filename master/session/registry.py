import logging
from master.lane import getLanesIndexed

sessions = set()

logger = logging.getLogger(__name__)


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

def trigger_vehicles_update(loop):
    """Trigger an update for all sessions."""
    global sessions
    logger.debug("Triggering vehicles update for all sessions.")
    for session in sessions:
        try:
            session.trigger_vehicle_update(loop)
        except Exception as e:
            session.logger.error(f"Failed to send vehicles update: {e}")
            remove_session(session)

def trigger_lanes_update(loop, updatedData):
    """Trigger an update for all sessions."""
    global sessions
    logger.debug("Triggering lanes update for all sessions.")
    for session in sessions:
        try:
            session.trigger_lane_update(loop, updatedData)
        except Exception as e:
            session.logger.error(f"Failed to send lanes update: {e}")
            remove_session(session)

def trigger_lanes_position(loop):
    """Trigger an update for all sessions."""
    global sessions
    logger.debug("Triggering lanes position update for all sessions.")
    for session in sessions:
        try:
            session.trigger_lane_position(loop)
        except Exception as e:
            session.logger.error(f"Failed to send lanes position: {e}")
            remove_session(session)