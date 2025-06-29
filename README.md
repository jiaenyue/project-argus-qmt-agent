# Data Agent Service

This service provides an API proxy for financial data, initially focusing on `xtquant` library functionalities.

## Features

- `/instrument_detail`: Fetches real-time contract information.

## Setup and Run

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the FastAPI application:**
    ```bash
    uvicorn data_agent_service.main:app --reload
    ```

## API Usage

### Get Instrument Detail

-   **Endpoint:** `/instrument_detail`
-   **Method:** `GET`
-   **Query Parameter:**
    -   `symbol` (string, required): The stock/contract symbol (e.g., "600519.SH").
-   **Example:**
    ```python
    import requests

    response = requests.get(
        "http://localhost:8000/instrument_detail",
        params={"symbol": "600519.SH"}
    )
    print(response.json())
    ```
