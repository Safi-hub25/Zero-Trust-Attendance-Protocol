import unittest

# --- The Logic Being Tested  ---
def evaluate_cosine_distance(score):
    """
    Returns True if the score is under the 0.25 threshold (Valid Match).
    Returns False if the score is 0.25 or higher (Spoof/Mismatch).
    """
    THRESHOLD = 0.25
    if score < THRESHOLD:
        return True
    else:
        return False

# --- The Unit Tests ---
class TestBiometricThresholds(unittest.TestCase):

    def test_valid_match_under_threshold(self):
        # Testing a highly confident match (e.g., 0.15)
        synthetic_score = 0.15
        result = evaluate_cosine_distance(synthetic_score)
        self.assertTrue(result, "Failed: 0.15 should be accepted as a valid match.")

    def test_spoof_over_threshold(self):
        # Testing a rejected match/spoof (e.g., 0.35)
        synthetic_score = 0.35
        result = evaluate_cosine_distance(synthetic_score)
        self.assertFalse(result, "Failed: 0.35 should be aggressively rejected.")
        
    def test_exact_boundary_condition(self):
        # Testing the exact threshold edge-case (0.25)
        synthetic_score = 0.25
        result = evaluate_cosine_distance(synthetic_score)
        self.assertFalse(result, "Failed: Exact threshold of 0.25 must be rejected.")

if __name__ == '__main__':
    unittest.main(verbosity=2)



    