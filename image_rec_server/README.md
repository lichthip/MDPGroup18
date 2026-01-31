## Local Development

To run the inference server locally using Docker, follow these steps:

1. **Navigate to the service directory:**

   ```bash
   cd image_rec_server
   ```

2. **Build the Docker image:**

   ```bash
   docker buildx build -t img_reg_api .
   ```

3. **Run the container:**

   ```bash
   docker run -p 8000:8000 img_reg_api
   ```

   The service is now running and listening on port 8000 on your local machine.
