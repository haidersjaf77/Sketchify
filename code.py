from flask import Flask, render_template_string, request, jsonify, send_file
import os
import cv2
import shutil
from threading import Thread
from werkzeug.serving import make_server

# Create Flask app
app = Flask(__name__)

# Folder to store uploaded and output images
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Function to convert image to pencil sketch
def convert_to_pencil_sketch(image_path):
    img = cv2.imread(image_path)
    
    if img is None:
        raise FileNotFoundError(f"Image not found at the path: {image_path}")

    gray_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    inverted_image = cv2.bitwise_not(gray_image)
    blurred_image = cv2.GaussianBlur(inverted_image, (21, 21), 0)
    inverted_blur = cv2.bitwise_not(blurred_image)
    pencil_sketch = cv2.divide(gray_image, inverted_blur, scale=256.0)
    
    return pencil_sketch

# Home route with interactive HTML
@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image to Pencil Sketch Converter</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(to right, #f0f0f0, #d9e4f5);
            margin: 0;
            padding: 20px;
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .container {
            max-width: 600px;
            margin: 30px auto;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
        }
        form {
            text-align: center;
        }
        input[type="file"] {
            margin: 20px auto;
            display: block;
        }
        button {
            padding: 10px 20px;
            font-size: 16px;
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        button:hover {
            background-color: #2980b9;
        }
        #preview, #sketch {
            max-width: 100%;
            margin: 20px auto;
            display: none;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        .actions {
            display: none;
            text-align: center;
            margin-top: 20px;
        }
        .loader {
            display: none;
            margin: 20px auto;
            border: 8px solid #f3f3f3;
            border-radius: 50%;
            border-top: 8px solid #3498db;
            width: 60px;
            height: 60px;
            animation: spin 2s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <h1>Image to Pencil Sketch Converter</h1>
    <div class="container">
        <form id="uploadForm">
            <label for="image">Upload an image:</label>
            <input type="file" id="image" name="image" accept="image/*" required>
            <button type="submit">Convert</button>
        </form>
        <img id="preview" src="" alt="Uploaded Image Preview">
        <div class="loader" id="loader"></div>
        <img id="sketch" src="" alt="Pencil Sketch">
        <div class="actions">
            <button id="save">Save</button>
            <button id="discard">Discard</button>
        </div>
    </div>

    <script>
        const form = document.getElementById('uploadForm');
        const imageInput = document.getElementById('image');
        const preview = document.getElementById('preview');
        const loader = document.getElementById('loader');
        const sketch = document.getElementById('sketch');
        const actions = document.querySelector('.actions');
        let filename = '';

        imageInput.addEventListener('change', () => {
            const file = imageInput.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    preview.src = e.target.result;
                    preview.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
        });

        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData();
            formData.append('image', imageInput.files[0]);

            loader.style.display = 'block';
            sketch.style.display = 'none';
            actions.style.display = 'none';

            fetch('/upload', {
                method: 'POST',
                body: formData,
            })
                .then((response) => response.json())
                .then((data) => {
                    if (data.sketch_image) {
                        sketch.src = data.sketch_image;
                        sketch.style.display = 'block';
                        actions.style.display = 'flex';
                        filename = data.filename;
                    } else {
                        alert(data.error || 'An error occurred.');
                    }
                    loader.style.display = 'none';
                })
                .catch((error) => {
                    console.error('Error:', error);
                    alert('An error occurred.');
                    loader.style.display = 'none';
                });
        });

        document.getElementById('save').addEventListener('click', () => {
            fetch('/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename }),
            })
                .then((response) => response.json())
                .then((data) => alert(data.message))
                .catch((error) => console.error('Error:', error));
        });

        document.getElementById('discard').addEventListener('click', () => {
            fetch('/discard', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename }),
            })
                .then((response) => response.json())
                .then((data) => {
                    alert(data.message);
                    sketch.style.display = 'none';
                    actions.style.display = 'none';
                    preview.style.display = 'none';
                })
                .catch((error) => console.error('Error:', error));
        });
    </script>
</body>
</html>
    ''')

# Route to handle image upload and pencil sketch conversion
@app.route('/upload', methods=['POST'])
def upload_image():
    # Check if an image file was uploaded
    if 'image' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['image']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file:
        # Save the uploaded file to the uploads folder
        input_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(input_path)

        # Convert the image to a pencil sketch
        sketch_image = convert_to_pencil_sketch(input_path)
        output_path = os.path.join(OUTPUT_FOLDER, 'sketch_' + file.filename)
        
        # Save the sketch image
        cv2.imwrite(output_path, sketch_image)

        # Return the path to the sketch image
        return jsonify({'sketch_image': '/outputs/' + 'sketch_' + file.filename, 'filename': file.filename})

# Route to serve output images
@app.route('/outputs/<filename>')
def output_file(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename))

# Route to handle saving the images
@app.route('/save', methods=['POST'])
def save_images():
    data = request.get_json()
    filename = data.get('filename')

    if not filename:
        return jsonify({'error': 'No filename provided'}), 400

    input_path = os.path.join(UPLOAD_FOLDER, filename)
    output_path = os.path.join(OUTPUT_FOLDER, 'sketch_' + filename)

    # Ensure the files exist
    if not os.path.exists(input_path):
        return jsonify({'error': f'File {input_path} not found'}), 404

    if not os.path.exists(output_path):
        return jsonify({'error': f'Sketch file {output_path} not found'}), 404

    # Debug: Print paths to check if they're correct
    print(f"Saving files: {input_path} and {output_path}")

    # Save both the original image and the pencil sketch to a separate directory for confirmation
    saved_upload_path = os.path.join(OUTPUT_FOLDER, 'saved_' + filename)
    saved_sketch_path = os.path.join(OUTPUT_FOLDER, 'saved_sketch_' + filename)

    try:
        # Copy the original uploaded image and the pencil sketch image
        shutil.copy(input_path, saved_upload_path)
        shutil.copy(output_path, saved_sketch_path)
        return jsonify({'message': 'Both images have been saved successfully.'})
    except Exception as e:
        # Debug: Catch any errors during the saving process
        print(f"Error during file saving: {e}")
        return jsonify({'error': 'An error occurred while saving the images'}), 500

# Flask server class to run the app in a separate thread
class FlaskServer(Thread):
    def __init__(self, app):
        Thread.__init__(self)
        self.srv = make_server('127.0.0.1', 5000, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        print("Starting Flask server on http://127.0.0.1:5000/")
        self.srv.serve_forever()

    def shutdown(self):
        self.srv.shutdown()

# Start the Flask app in a separate thread
server = FlaskServer(app)
server.start()
