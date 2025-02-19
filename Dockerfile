FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set the environment variable for the bot token
ENV TOKEN=<your_bot_token_here>

# Command to run the bot
CMD ["python", "bot.py"]