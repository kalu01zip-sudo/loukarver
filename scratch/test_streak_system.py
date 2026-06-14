import asyncio
import sys
import os
import io
from datetime import datetime
from fastapi import UploadFile

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.streak import streak_system
from app.schemas.ritual import RitualCompleteRequest, RitualType

async def run_test():
    # Initialize indexes
    print("Initializing indexes...")
    await streak_system.init_indexes()
    
    # Create a unique dummy user
    dummy_email = f"test_user_{int(datetime.utcnow().timestamp())}@example.com"
    dummy_user = {
        "email": dummy_email,
        "name": "Test User",
        "current_streak": 0,
        "longest_streak": 0,
        "partner": {
            "user_id": "603728192837482937482938",
            "name": "Sweetheart",
            "city_name": "London",
            "relationship_start_date": "2025-01-01",
            "is_long_distance": True
        }
    }
    user_res = await streak_system.users_collection.insert_one(dummy_user)
    user_id = str(user_res.inserted_id)
    print(f"Created dummy user: {user_id}")

    saved_files = []

    try:
        # Create a mock file
        mock_file_content = b"fake image/photo data"
        mock_file = UploadFile(
            file=io.BytesIO(mock_file_content),
            filename="partner_photo.png"
        )

        # Complete ritual 1 with a file
        req1 = RitualCompleteRequest(
            ritual_type=RitualType.photo,
            timezone="UTC",
            text="Appreciating my partner with a photo"
        )
        print("Completing first ritual with a file...")
        res1 = await streak_system.mark_ritual_complete(user_id, req1, file=mock_file)
        print("First completion result:", res1)
        
        # We need the inserted ritual ID to test update/delete
        # Let's find the document in DB
        doc1 = await streak_system.rituals_collection.find_one({"user_id": user_id, "ritual_type": "photo"})
        ritual_id_1 = str(doc1["_id"])
        
        if res1.get("file_path"):
            saved_files.append(res1["file_path"].lstrip("/"))

        # Complete ritual 2 without a file
        req2 = RitualCompleteRequest(
            ritual_type=RitualType.goodnight,
            timezone="UTC",
            text="Saying goodnight"
        )
        print("Completing second ritual...")
        res2 = await streak_system.mark_ritual_complete(user_id, req2)
        print("Second completion result:", res2)
        
        doc2 = await streak_system.rituals_collection.find_one({"user_id": user_id, "ritual_type": "goodnight"})
        ritual_id_2 = str(doc2["_id"])

        # Asserts on returned ritual_id
        assert res1["success"] is True
        assert res1["ritual_id"] == ritual_id_1
        assert "time" in res1 and res1["time"] is not None
        assert res1["time_name"] in ["morning", "afternoon", "evening", "night"]
        assert res2["success"] is True
        assert res2["ritual_id"] == ritual_id_2
        assert "time" in res2 and res2["time"] is not None
        assert res2["time_name"] in ["morning", "afternoon", "evening", "night"]

        # Check file exists on disk
        local_file_path = res1["file_path"].lstrip("/")
        assert os.path.exists(local_file_path) is True

        # ---- TEST UPDATE (PATCH) ----
        print("Testing update (PATCH)...")
        new_mock_content = b"updated fake image/photo data"
        new_mock_file = UploadFile(
            file=io.BytesIO(new_mock_content),
            filename="new_photo.png"
        )
        
        update_res = await streak_system.update_ritual(
            user_id=user_id,
            ritual_id=ritual_id_1,
            ritual_type=RitualType.appreciation,
            text="Updated text",
            file=new_mock_file
        )
        print("Update result:", update_res)
        
        if update_res.get("file_path"):
            saved_files.append(update_res["file_path"].lstrip("/"))

        assert "time" in update_res and update_res["time"] is not None
        assert update_res["time_name"] in ["morning", "afternoon", "evening", "night"]

        # Assert old file deleted and new file exists
        assert os.path.exists(local_file_path) is False
        new_local_path = update_res["file_path"].lstrip("/")
        assert os.path.exists(new_local_path) is True
        with open(new_local_path, "rb") as f:
            assert f.read() == new_mock_content

        # Verify DB doc updated
        updated_doc1 = await streak_system.rituals_collection.find_one({"_id": doc1["_id"]})
        assert updated_doc1["ritual_type"] == "appreciation"
        assert updated_doc1["text"] == "Updated text"
        assert updated_doc1["file_path"] == update_res["file_path"]

        # ---- TEST ERROR CASES ----
        print("Testing error cases...")
        # 1. Invalid ID format
        try:
            await streak_system.update_ritual(user_id, "invalid_id")
            assert False, "Should raise ValueError for invalid ID format"
        except ValueError:
            pass
            
        # 2. Ritual not found
        try:
            await streak_system.update_ritual(user_id, "603728192837482937482938")
            assert False, "Should raise ValueError for non-existent ritual"
        except ValueError:
            pass
            
        # 3. Permission denied (different user ID)
        try:
            await streak_system.update_ritual("603728192837482937482939", ritual_id_1)
            assert False, "Should raise PermissionError"
        except PermissionError:
            pass

        # ---- TEST DELETE ----
        print("Testing delete...")
        # Delete ritual 2 (no file)
        delete_res_2 = await streak_system.delete_ritual(user_id, ritual_id_2)
        print("Delete ritual 2 result:", delete_res_2)
        assert delete_res_2["success"] is True
        
        # Verify document count is 1
        docs_count_after_del = await streak_system.rituals_collection.count_documents({"user_id": user_id})
        assert docs_count_after_del == 1

        # Delete ritual 1 (with file)
        delete_res_1 = await streak_system.delete_ritual(user_id, ritual_id_1)
        print("Delete ritual 1 result:", delete_res_1)
        assert delete_res_1["success"] is True

        # Verify file deleted from disk
        assert os.path.exists(new_local_path) is False
        
        # Verify document count is 0
        docs_count_final = await streak_system.rituals_collection.count_documents({"user_id": user_id})
        assert docs_count_final == 0

        # Verify streak updated in user doc (should be 0 after deleting all)
        user_after = await streak_system.users_collection.find_one({"_id": user_res.inserted_id})
        assert user_after["current_streak"] == 0

        print("\nALL TESTS PASSED!")

    finally:
        # Cleanup
        print("Cleaning up dummy data...")
        await streak_system.users_collection.delete_one({"_id": user_res.inserted_id})
        await streak_system.rituals_collection.delete_many({"user_id": user_id})
        for path in saved_files:
            if os.path.exists(path):
                os.remove(path)
                print(f"Removed saved file: {path}")
        print("Cleanup done.")

if __name__ == "__main__":
    asyncio.run(run_test())
