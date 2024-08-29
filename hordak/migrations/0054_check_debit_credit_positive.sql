-- ----
ALTER TABLE hordak_leg ADD CONSTRAINT hordak_leg_chk_debit_positive CHECK (debit > 0);
-- - reverse:
ALTER TABLE hordak_leg DROP CONSTRAINT hordak_leg_chk_debit_positive;

-- ----
ALTER TABLE hordak_leg ADD CONSTRAINT hordak_leg_chk_credit_positive CHECK (credit > 0);
-- - reverse:
ALTER TABLE hordak_leg DROP CONSTRAINT hordak_leg_chk_credit_positive;
