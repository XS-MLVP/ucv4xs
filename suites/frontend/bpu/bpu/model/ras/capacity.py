"""Two call identities and one capacity/reclamation lifecycle, not a slot sweep."""
CAPACITY=32
PRESERVED=CAPACITY-2 # Restore below the registered near-overflow threshold.
POSITION=15
OLD_CALL=0x40018000
OLD_RETURN=OLD_CALL+16
NEW_CALL=OLD_CALL+0x200
NEW_RETURN=NEW_CALL+16
RESUMED_CALLS=6 # Keep a new-address group after draining and cancelling younger work.


def call_address(pc):
    # Integrated PC is halfwords; RAS program addresses are bytes.
    return ((pc//16)*16+POSITION+1)*2
