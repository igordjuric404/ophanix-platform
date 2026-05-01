DROP INDEX IF EXISTS idx_trust_card_revocations_card;
DROP TABLE IF EXISTS trust_card_revocations;
DROP INDEX IF EXISTS idx_trust_cards_agent_status;
DROP TABLE IF EXISTS trust_cards;
DELETE FROM schema_migrations WHERE version = '0010';
