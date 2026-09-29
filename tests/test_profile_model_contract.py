"""Behavioral tests for the pre-fit ENOE profile-model contract."""

from __future__ import annotations

import copy
import unittest

from scripts.profile_model_contract import ModelContractError, load_contract, validate_contract


class ProfileModelContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_repository_contract_is_valid_and_does_not_authorize_fitting(self):
        result = validate_contract(self.contract)

        self.assertTrue(result["contract_validated"])
        self.assertEqual(result["fit_status"], "contract_only")
        self.assertEqual(result["evaluation_periods"], ["2026Q1", "2026Q2"])

    def test_aggregate_profile_cannot_replace_person_quarter_model_input(self):
        contract = copy.deepcopy(self.contract)
        contract["source"]["prepared_view"] = "analysis.enoe_weighted_profile"

        with self.assertRaisesRegex(ModelContractError, "prepared person-quarter view"):
            validate_contract(contract)

    def test_contract_rejects_2026_as_a_training_period(self):
        contract = copy.deepcopy(self.contract)
        contract["temporal_split"]["development_periods"].append("2026Q1")

        with self.assertRaisesRegex(ModelContractError, "temporal periods"):
            validate_contract(contract)

    def test_contract_rejects_a_semantically_unresolved_formality_input(self):
        contract = copy.deepcopy(self.contract)
        contract["fit_features"][0]["source_columns"].append("emp_ppal")

        with self.assertRaisesRegex(ModelContractError, "prohibited field"):
            validate_contract(contract)

    def test_contract_rejects_fitting_or_substantive_imputation(self):
        fit_contract = copy.deepcopy(self.contract)
        fit_contract["fit_status"] = "approved_to_fit"
        missing_contract = copy.deepcopy(self.contract)
        missing_contract["missingness"]["imputation"] = "mode"

        with self.assertRaisesRegex(ModelContractError, "must not authorize fitting"):
            validate_contract(fit_contract)
        with self.assertRaisesRegex(ModelContractError, "prohibit substantive imputation"):
            validate_contract(missing_contract)

    def test_contract_rejects_removing_the_2026_training_prohibition(self):
        contract = copy.deepcopy(self.contract)
        contract["out_of_scope"].remove("2026_training")

        with self.assertRaisesRegex(ModelContractError, "out-of-scope protections"):
            validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
