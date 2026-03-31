# Gen AI Coding Best Practices With Examples

Best practices for coding with an LLM (mostly on GPT 4o). Examples from real life scenarios and from Deeplearning.ai.

## Setup

1. Create a virtual environment:
   ```bash
   python3 -m venv venv
   ```

2. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
Every file has a "*** Prompt" section to indicate which prompts where used to generate or add functionality like tests to it. There can be multiple prompts, indicating the iterative development with the LLM.


## Flask Apps
There are flask apps with *FlaskApp.py names. To run them
```bash
flask --app userFlaskApp.py run
```

Then run Curl commands to interact with the app.
```bash
curl -X GET http://127.0.0.1:5000/users
```


## Pytests
All tests are located under /test/ folder. To run pytests
```bash
pytest tests/test_taskManager.py
```