# Project Roadmap & TODOs

## High Priority

### 1. Enforce Inheritance for Scrapers

- [ ] Update all 18 existing scraper files (e.g., `pandamaster.py`, `firekirin.py`, etc.) to explicitly inherit from `BaseGameScraper`.
- [ ] Ensure all methods strictly match the type hints defined in `app/services/scrapers/base.py`.

### 2. Optimize Browser Management (Performance)

- [ ] **Problem**: Currently, every task launches a new Chrome instance, taking 2-5 seconds start-up time per request.
- [ ] **Solution**: Implement a **Browser Pool** or Session Manager.
  - Since Celery workers are long-lived processes, cache the `Scraper` instance (and its `driver`) globally within the worker process.
  - Implement a health check mechanism to reuse the driver if it's still responsive, or restart it if needed.
  - Consider using a remote WebDriver container (Selenium Grid) for better scaling.

## Code Quality & Reliability

### 3. Centralized Logging & Error Handling

- [ ] Create a decorator `@handle_scraper_errors` in the base class or a utility file.
- [ ] Apply this decorator to scraper methods to standardize:
  - Exception logging (with tracebacks)
  - Automatic screenshot capture on error
  - Retry logic for transient failures (e.g., `StaleElementReferenceException`)
- [ ] Remove repetitive `try-except` blocks from individual scraper implementations.

### 4. Testing

- [ ] Add unit tests for `app/services/scrapers/factory.py` to ensure all registered games load correctly.
- [ ] Add unit tests for `app/worker/tasks.py` (mocking the scrapers) to verify the factory usage and async execution logic.
- [ ] Add integration tests for key scrapers (using a mock server or actual test accounts if available).

## Documentation

- [ ] Generate API documentation updates (if needed) for any new endpoints.
- [ ] Maintain `docs/architecture_improvements.md` as new patterns are adopted.
