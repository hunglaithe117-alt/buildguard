# BuildGuard - Risk-Based CI/CD Pipeline Analyzer

BuildGuard is a comprehensive system designed to analyze, assess, and mitigate risks in CI/CD pipelines. It integrates with GitHub, SonarQube, and other tools to provide real-time insights into build quality, security vulnerabilities, and team dynamics.

## 🚀 Key Features

*   **Risk Assessment**: Automatically calculates a risk score for each build based on code churn, test coverage, and historical data.
*   **SonarQube Integration**: Triggers and retrieves SonarQube scans to analyze code quality and security.
*   **GitHub Integration**: Seamlessly connects with GitHub Apps to monitor repositories, pull requests, and workflow runs.
*   **Shadow Mode**: Allows testing risk policies without blocking actual builds (dry-run).
*   **Dashboard**: A modern Next.js frontend for visualizing build risks, managing repositories, and configuring policies.
*   **Scalable Architecture**: Microservices-based design with separate API, Worker, and Frontend services.

## 🏗 System Architecture

The project is organized as a monorepo with the following components:

*   **`services/app-backend`**: The core REST API (FastAPI) handling user requests, GitHub webhooks, and data retrieval.
*   **`services/pipeline-backend`**: The heavy-lifting worker (Celery) responsible for cloning code, running scans, and processing data.
*   **`services/app-frontend`**: The user interface (Next.js) for interacting with the system.
*   **`packages/python-common`**: Shared Python library containing domain models and utility functions.
*   **Infrastructure**: MongoDB (Data), Redis (Cache/Queue), RabbitMQ (Broker), SonarQube (Analysis).

## 🛠 Prerequisites

*   Docker & Docker Compose
*   Node.js 18+ (for local frontend dev)
*   Python 3.10+ (for local backend dev)
*   `uv` (Python package manager)

## 🚦 Getting Started

### 1. Configuration

Create a `.env` file in the root directory (copy from `.env.example` if available) and configure the following:

```bash
# GitHub App Credentials
GITHUB_APP_ID=your_app_id
GITHUB_APP_PRIVATE_KEY=your_private_key
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# SonarQube (Optional if using embedded instance)
SONAR_TOKEN=your_sonar_token
```

### 2. Running with Docker Compose (Recommended)

To start the entire system:

```bash
docker compose up -d
```

Access the services:
*   **Frontend**: http://localhost:3000
*   **API Docs**: http://localhost:8000/docs
*   **SonarQube**: http://localhost:9000 (Default login: admin/admin)

### 3. Distributed Deployment (Optional)

If you want to run the heavy backend on a server and the frontend locally:

**On the Server:**
```bash
# Run everything EXCEPT the frontend
docker compose up -d --scale app-frontend=0
```

**On Local Machine:**
1.  Update `.env` or environment variables:
    ```bash
    NEXT_PUBLIC_API_URL=http://<SERVER_IP>:8000/api
    ```
2.  Run the frontend:
    ```bash
    docker compose -f docker-compose.frontend.yml up -d
    ```

## 📦 Development

### Backend (`services/app-backend` & `services/pipeline-backend`)

We use `uv` for dependency management.

```bash
cd services/app-backend
uv sync
uv run uvicorn app.main:app --reload
```

### Frontend (`services/app-frontend`)

```bash
cd services/app-frontend
npm install
npm run dev
```

## 🤝 Contributing

Please read `CONTRIBUTING.md` (if available) for details on our code of conduct and the process for submitting pull requests.

## 📄 License

[MIT License](LICENSE)
