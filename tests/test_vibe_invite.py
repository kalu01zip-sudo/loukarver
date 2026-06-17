import asyncio
import sys
import os
from datetime import datetime, timezone

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.vibe_check import vibe_check_service
from app.schemas.vibe_check import VibeCheckProfileCreate

async def run_test():
    print("Initializing indexes...")
    await vibe_check_service.init_indexes()
    
    # Setup dummy users
    user_a_id = "test_invite_a_" + str(int(datetime.now(timezone.utc).timestamp()))
    user_b_id = "test_invite_b_" + str(int(datetime.now(timezone.utc).timestamp()))
    
    await vibe_check_service.create_or_update_profile(user_a_id, VibeCheckProfileCreate(name="User A"))
    await vibe_check_service.create_or_update_profile(user_b_id, VibeCheckProfileCreate(name="User B"))
    
    try:
        # Generate
        invite = await vibe_check_service.generate_invite(user_a_id)
        assert invite.invite_code is not None
        
        # Validate
        val = await vibe_check_service.validate_invite(invite.invite_code)
        assert val.valid is True
        
        # Accept
        accept = await vibe_check_service.accept_invite(user_b_id, invite.invite_code)
        assert accept.success is True
        
        # Verify
        conns = await vibe_check_service.get_connections(user_a_id)
        assert any(c["user_id"] == user_b_id for c in conns)
        
        print("Vibe Check Invite System Test: PASSED")
    finally:
        # Cleanup
        await vibe_check_service.profiles.delete_many({"user_id": {"$in": [user_a_id, user_b_id]}})
        await vibe_check_service.connections.delete_many({"user_id": {"$in": [user_a_id, user_b_id]}})
        await vibe_check_service.connections.delete_many({"partner_id": {"$in": [user_a_id, user_b_id]}})
        await vibe_check_service.invites.delete_many({"inviter_id": user_a_id})

if __name__ == "__main__":
    asyncio.run(run_test())
