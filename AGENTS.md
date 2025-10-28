# GitHub Issue Comment Relay Feasibility

## Requirement Summary
- Build a Python webhook handler using FastAPI that runs identically in both local development and Azure Web App production environments.
- Handle GitHub `issue_comment` events by filtering comments containing `@FoundryAgent` (anywhere in the comment). Only the text after the first `@FoundryAgent` mention is forwarded to the agent, with leading punctuation and whitespace removed.
- Ensure the webhook response completes within GitHub's ~10 second SLA by returning `202 Accepted` promptly and deferring the agent/GitHub work to FastAPI background tasks.
- Forward the stripped comment content to an Azure AI Foundry Agent (via the `agent-framework-azure-ai` package) and capture the agent's response body.
- Provide a dedicated Python file responsible for creating the Azure AI Foundry Agent using Python package `agent-framework-azure-ai`.
- Post the agent response back to the originating GitHub issue via `POST api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments`, referencing the triggering message for context.
- Operate inside a local `venv` for development with the same FastAPI codebase deployed to Azure Web App for production.
- Allow local execution via `python main.py`, with webhook debugging performed through ngrok tunneling.
- Protect the endpoint with GitHub webhook HMAC validation so only the target GitHub repo's webhook can invoke it.
- Automate deployments to Azure Web App using GitHub Actions workflows.
- Follow a test-driven development (TDD) workflow: author unit tests before implementing features, and ensure the entire suite passes after each task.
- Document GitHub webhook setup: create the webhook, specify the Azure Web App URL, configure webhook secret for HMAC validation, and store credentials securely.The document format is markdown.
- Document Azure Web App provisioning with az cli: create the app service plan and web app in linux, configure environment settings, and set up continuous deployment.The document format is markdown.
- Document ngrok configuration: install ngrok, map the local FastAPI port, and update GitHub webhook URL during local testing.The document format is markdown.

## Feasibility Overview
- GitHub delivers `issue_comment` webhooks that include the full comment body, so detecting entries that contain `@FoundryAgent` anywhere is straightforward. The service extracts the text after the first mention and trims leading punctuation for clean prompts.
- Azure AI Foundry Agent (invoked through the `agent-framework-azure-ai` SDK) accepts arbitrary prompts, enabling relay of the stripped comment content and receiving a reply payload.
- The webhook handling, Azure AI Foundry Agent call, and GitHub reply logic live in a unified FastAPI application that runs identically in local development and Azure Web App production environments.
- FastAPI's `BackgroundTasks` feature allows immediate `202 Accepted` responses while processing agent calls and GitHub replies asynchronously, satisfying GitHub's webhook SLA requirements.
- Azure Web App provides a simple deployment target with built-in HTTPS, environment variable management, and GitHub Actions integration.
- The unified codebase approach simplifies development, testing, and deployment by using the same FastAPI application in all environments.

## Feasibility Analysis Per Requirement
- **Unified FastAPI application**: The entire webhook handler, including parsing, filtering, signature validation, agent call, and GitHub reply logic, runs in a single FastAPI application used for both local development and Azure Web App production deployment.
- **Event scope**: Process only `issue_comment` notifications where `action == "created"`; respond immediately with `200` for any other action to avoid unnecessary downstream work.
- **Forwarding to Azure AI Foundry Agent**: Using the `agent-framework-azure-ai` SDK, the service wraps the parsed comment text in an agent invocation with the right credentials (key or token); FastAPI's async support handles the agent call efficiently.
- **Replying back on GitHub**: Using a GitHub App or PAT, the service calls `POST api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments` to publish the agent response on the same issue while referencing the triggering comment for context.
- **Local `venv` + `python main.py` execution**: Developers activate the virtual environment and run `python main.py` to start the FastAPI server with `uvicorn`, enabling local debugging with the same codebase used in production.
- **Webhook debugging with ngrok**: ngrok exposes the local FastAPI endpoint securely; GitHub can target the temporary HTTPS URL while the service runs locally, enabling end-to-end testing.
- **Production on Azure Web App**: Azure Web App hosts the same FastAPI application with environment-based configuration; GitHub webhook secret validation provides security without requiring additional authentication layers.
- **Deployment via GitHub Actions**: GitHub Actions supports Azure Web App deployments using `azure/webapps-deploy`; the workflow can build the package, run tests, and publish using stored Azure credentials or OIDC.
- **TDD enforcement**: Python unit tests (e.g., `pytest`) can run quickly in CI and locally; failing builds in GitHub Actions if tests fail ensures no task completes without a passing suite.

## Recommended Technology Choices
- **Python runtime**: Use Python 3.10+ with a local `venv` to isolate dependencies for both development and deployment.
- **FastAPI web framework**: Use FastAPI for both local development and Azure Web App production deployment, providing a unified codebase with native async support and built-in request validation.
- **Background task handling**: Use FastAPI's `BackgroundTasks` to defer agent invocation and GitHub reply logic, allowing the webhook endpoint to return `202 Accepted` immediately while processing continues asynchronously.
- **Agent SDK**: Use the `agent-framework-azure-ai` package to construct and invoke the Azure AI Foundry Agent, centralizing credentials and prompt settings in a dedicated helper module.
- **Azure deployment**: Deploy to Azure Web App (Linux) with Python 3.10+ runtime, using the same FastAPI application code that runs locally.
- **Entry point**: Implement `main.py` to configure logging, load environment variables, and start `uvicorn.run(app, host="0.0.0.0", port=8000)` for both local and production execution.
- **GitHub integration**: Authenticate outbound replies with a GitHub App or PAT to call `POST /repos/{owner}/{repo}/issues/{issue_number}/comments`, posting the Azure AI Foundry Agent response as a new comment while referencing the triggering message for context.
- **CI/CD**: Configure a GitHub Actions workflow that runs tests, packages the application, and deploys to Azure Web App using `azure/webapps-deploy` with OIDC or publish profile stored in repository secrets.
- **Testing strategy**: Use `pytest` with coverage thresholds and include mocks for GitHub and Azure AI Foundry Agent calls (mocking the `agent-framework-azure-ai` client); enforce test execution both locally and inside the CI workflow before deployment steps.
- **Webhook security**: Validate GitHub webhook signatures using the HMAC secret to ensure requests originate from GitHub; store the secret in Azure Web App application settings. Use the `X-Hub-Signature-256` header (HMAC SHA-256 over the raw payload); if the header is missing or does not match, return `401 Unauthorized`.

## Operational Notes
- Store secrets (GitHub webhook HMAC secret, GitHub App credentials, Azure AI Foundry agent key) in environment variables; never commit them.
- Validate GitHub webhook signatures using HMAC to ensure only authorized GitHub requests reach the handler.
- Log key stages (receipt, filtered match, Azure agent call, reply post) to aid diagnostics. For local development, write logs to a file; for production on Azure, direct logs to stdout/stderr for integration with cloud logging services. 
- **Error handling and retry strategy**: If the Azure AI Foundry Agent call fails or times out, automatically retry once before reporting failure; if both attempts fail, just return without posting a comment.

## Programming Workflow

### Protected Directories
- **DO NOT modify files** in the following directories:
  - `.github/prompts/` - Reserved for GitHub configuration prompts
  - `.specify/templates/` - Reserved for Specify templates
  - `.specify/scripts/` - Reserved for Specify automation scripts
- These directories contain critical configuration and automation files that must remain unchanged during development.

### Mandatory Test-Driven Development (TDD)
- **MUST follow TDD**: Write unit tests before implementing any feature or functionality.
- **Red-Green-Refactor cycle**:
  1. **Red**: Write a failing test that defines the desired behavior
  2. **Green**: Implement the minimum code needed to make the test pass
  3. **Refactor**: Improve code quality while keeping tests green
- **Test coverage**: Maintain comprehensive test coverage for all modules; aim for >80% coverage.
- **No implementation without tests**: Do not proceed to implementation until corresponding tests are written and initially failing.

### Requirement Clarification
- **Ask when uncertain**: If any requirement is ambiguous, unclear, or potentially conflicting, stop and ask clarifying questions before proceeding
- **Confirm expectations**: Validate assumptions about expected behavior, edge cases, and error handling with stakeholders
- **Document decisions**: Record clarifications and decisions in comments or documentation for future reference

### Code Verification and Quality Assurance
After completing any code modification:
1. **Self-review**: Critically examine your own code changes
   - Check for logic errors, edge cases, and potential bugs
   - Verify code follows Python best practices and project conventions
   - Ensure proper error handling and logging are in place
2. **Challenge assumptions**: Question your implementation choices
   - Could this fail under specific conditions?
   - Are there performance implications?
   - Is the code maintainable and readable?
3. **Run the full test suite**: Execute all unit tests to ensure nothing is broken
   ```bash
   pytest tests/ -v --cov=app
   ```
4. **Verify test coverage**: Ensure new code is adequately tested
5. **Check for regressions**: Confirm existing functionality still works as expected
6. **Only proceed when all tests pass**: Do not consider a task complete until the entire test suite is green


## Local and Cloud Execution
- **Local development**: Activate the `venv`, launch the FastAPI application with `python main.py`, and tunnel the local port via ngrok so GitHub can deliver webhook payloads for debugging; inspect payloads using ngrok's request inspector to aid troubleshooting.
- **Azure Web App**: Deploy the same FastAPI application to Azure Web App (Linux) with Python runtime; configure application settings for secrets and environment variables; the production endpoint uses the Web App's default HTTPS URL registered in GitHub webhook settings.
- **GitHub Actions**: Define a workflow (e.g., `.github/workflows/deploy.yml`) that authenticates to Azure, runs the test suite, builds the application package, and executes the Azure Web App Deploy action against the target web app.

## Implementation Phases

### Phase 1[Completed]: Project Foundation + Agent Module
**Objective**: Establish project structure and implement Azure AI Foundry Agent integration module with test coverage.

**Tasks**:
- Create project structure (venv, requirements.txt, directory layout)
- Implement agent module (`app/agent.py`) for creating and invoking Azure AI Foundry Agent using `agent-framework-azure-ai` package. there should be two functions: one for creating the agent instance with credentials from environment variables, and another for invoking the agent with a prompt and returning the response. The create function should printout the agent id of the created agent.
- The created agent should support Context7 MCP server, and grounded bing search.
- Write unit tests for agent module (mock `agent-framework-azure-ai` SDK calls)
- Provide local environment variable configuration guide (.env.example)
- Ensure all tests pass before proceeding to Phase 2

**Deliverables**:
- `app/agent.py` - Agent creation and invocation logic
- `tests/test_agent.py` - Unit tests with mocked agent calls
- `requirements.txt` - Python dependencies including `agent-framework-azure-ai`, `fastapi`, `pytest`
- `.env.example` - Template for required environment variables
- Documentation for setting up local development environment
- Documentation for how to call the agent.py module to create an agent and invoke it with a prompt

### Phase 2[Completed]: FastAPI Webhook Handler + TDD
**Objective**: Implement the complete webhook handling system following test-driven development workflow.

**Tasks**:
- Write unit tests first for:
  - GitHub webhook signature validation (HMAC)
  - `@FoundryAgent` comment filtering logic (contains match, extract text after mention, trim leading punctuation)
  - Background task processing flow
  - GitHub API comment posting
- Implement FastAPI application (`main.py`) with uvicorn entry point
- Implement GitHub webhook HMAC signature validation, if validatation fails, return 401 Unauthorized
- Implement `@FoundryAgent` comment filtering in webhook handler to match when the mention appears anywhere, and pass only the cleaned text after the mention to the agent.
- Implement FastAPI BackgroundTasks for async agent invocation and GitHub reply
- Implement GitHub API integration for posting agent responses
- Ensure all tests pass after implementation

**Deliverables**:
- `main.py` - FastAPI application entry point
- `app/webhook.py` - Webhook handler and routing logic
- `app/github.py` - GitHub API integration module
- `app/security.py` - HMAC signature validation
- `tests/test_webhook.py` - Webhook handler tests
- `tests/test_github.py` - GitHub API integration tests
- `tests/test_security.py` - Security validation tests

### Phase 3[Completed]: Local Development & Debugging Documentation
**Objective**: Provide comprehensive documentation for local development, testing, and debugging workflows.

**Tasks**:
- Document GitHub webhook configuration (webhook creation, secret setup, payload URL)
- Document local environment variable configuration and updates
- Document ngrok installation, port tunneling setup, and webhook URL configuration
- Document local debugging workflow (ngrok inspector, log inspection)
- Document running unit tests locally with pytest
- Document end-to-end local testing procedure

### Phase 4: Production Deployment
**Objective**: Deploy the application to Azure Web App with continuous deployment pipeline and production monitoring.

**Tasks**:
- Document Azure Web App provisioning using az cli (App Service Plan, Web App creation on Linux)
- Create GitHub Actions workflow file with:
  - Test execution step (fail build if tests fail)
  - Application packaging
  - Azure Web App deployment using `azure/webapps-deploy` action
- Document Azure Web App environment variable configuration (secrets, agent credentials, agent id)
- Configure GitHub webhook to point to Azure Web App production URL
- Verify end-to-end production workflow

**Deliverables**:
- `docs/azure-web-app-deployment.md` - Azure Web App provisioning guide using az cli. Provide the steps to configure environment variable settings in azure web app
- `.github/workflows/deploy.yml` - GitHub Actions CI/CD workflow


