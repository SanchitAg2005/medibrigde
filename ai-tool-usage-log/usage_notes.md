# AI Tool Usage Log

This directory logs the use of the **Antigravity AI coding assistant** (developed by the Google DeepMind team) in pair programming, refactoring, and verifying the MediBridge platform.

## Scope of AI Assistance
* **System Design**: Assisted in structuring the modular Django application layer layout, resolving architectural separations, and modeling the relational schema.
* **Concurrency Locking**: Guided the implementation of the database row-level lock (`select_for_update`) to prevent double-booking slot races.
* **Serverless Dispatcher**: Drafted the serverless handlers and async task polling worker commands.
* **Visual Theme Refactoring**: Performed contrast, spacing, and styling conversions to replace dark overlays with a clean clinical green/white color system.
* **Dashboard Reorganization**: Automated the separation of the patient dashboard timeline and the new dedicated doctor booking wizards.
* **Testing & Quality Assurance**: Accelerated creation of the Django mock integrations, validation tests, and setup scripts.
