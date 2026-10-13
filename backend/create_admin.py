from pymongo import MongoClient

from app.config import get_settings
from app.auth import hash_password


# ============================================================
# CARE+
# ADMIN ACCOUNT CREATOR
# ============================================================

settings = get_settings()


# ============================================================
# ADMIN CREDENTIALS
# ============================================================

EMAIL = "admin@gmail.com"

PASSWORD = "Admin@12345"

ROLE = "admin"


# ============================================================
# CONNECT TO MONGODB
# ============================================================

client = MongoClient(
    settings.mongodb_uri,
    serverSelectionTimeoutMS=5000,
)


try:

    # --------------------------------------------------------
    # VERIFY DATABASE CONNECTION
    # --------------------------------------------------------

    client.admin.command("ping")

    print("MongoDB connection successful.")


    # --------------------------------------------------------
    # GET DATABASE
    # --------------------------------------------------------

    db = client.get_database()


    # --------------------------------------------------------
    # USERS COLLECTION
    # --------------------------------------------------------

    users_collection = db["users"]


    # --------------------------------------------------------
    # CHECK EXISTING ACCOUNT
    # --------------------------------------------------------

    existing = users_collection.find_one(
        {
            "email": EMAIL
        }
    )


    # ========================================================
    # ACCOUNT ALREADY EXISTS
    # ========================================================

    if existing:

        existing_role = str(
            existing.get(
                "role",
                ""
            )
        ).strip().lower()


        print()
        print(
            "==================================="
        )

        print(
            "ACCOUNT ALREADY EXISTS"
        )

        print(
            "==================================="
        )

        print(
            "Email:",
            existing.get(
                "email"
            )
        )

        print(
            "Role:",
            existing_role or "not set"
        )


        # ----------------------------------------------------
        # VERIFY ADMIN ROLE
        # ----------------------------------------------------

        if existing_role == "admin":

            print()
            print(
                "This account is already an ADMIN."
            )

            print(
                "No changes were made."
            )


        else:

            print()
            print(
                "WARNING:"
            )

            print(
                "This email exists, but it is NOT an admin account."
            )

            print(
                "No changes were made."
            )

            print(
                "Existing role:",
                existing_role or "not set"
            )


    # ========================================================
    # CREATE NEW ADMIN
    # ========================================================

    else:

        password_hash = hash_password(
            PASSWORD
        )


        result = users_collection.insert_one(
            {
                "email": EMAIL,

                "password_hash":
                    password_hash,

                "role":
                    ROLE,
            }
        )


        print()
        print(
            "==================================="
        )

        print(
            "ADMIN CREATED"
        )

        print(
            "==================================="
        )

        print(
            "Email   :",
            EMAIL
        )

        print(
            "Password:",
            PASSWORD
        )

        print(
            "Role    :",
            ROLE
        )

        print(
            "MongoDB ID:",
            result.inserted_id
        )

        print()
        print(
            "You can now login to the Care+ Admin Dashboard."
        )


# ============================================================
# DATABASE ERROR
# ============================================================

except Exception as error:

    print()
    print(
        "==================================="
    )

    print(
        "ADMIN CREATION FAILED"
    )

    print(
        "==================================="
    )

    print(
        "Error:",
        error
    )

    print()
    print(
        "Check your MongoDB connection and .env configuration."
    )


# ============================================================
# CLOSE DATABASE CONNECTION
# ============================================================

finally:

    client.close()

    print()
    print(
        "MongoDB connection closed."
    )