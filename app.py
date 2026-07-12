import os

from flask import Flask, request, jsonify
import importlib

pipeline = importlib.import_module("04_rag_pipeline")


app = Flask(__name__)

@app.route('/ask', methods=['POST'])
def user_question():
    data = request.get_json()
    question = data.get('question')

    if not question:
        response = {
            "success": False,
            "status_code": 400,
            "message": "Question is missing from the body"
        }
        return jsonify(response), 400
    
    embedding = pipeline.embed(question)
    results = pipeline.search(embedding)

    chunk = []
    for result in results:
        chunk.append(result["content"])
        
    answer = pipeline.build_prompt(question, chunk)
    print(answer)
    return jsonify({"answer": answer}), 200

@app.route('/health', methods=['GET'])
def health_check():
    response = {
        "success": True,
        "status_code": 200,
        "message": "Service is up and running"
    }
    return jsonify(response), 200
  
# for 404 - not found    
@app.errorhandler(404)
def not_found(error):
    response = {
        "success": False,
        "status_code": 404,
        "message": "Resource not found"
    }
    return jsonify(response), 404

# for 405 not allowed methods
@app.errorhandler(405)
def method_not_allowed(error):
    response = {
        "success": False,
        "status_code": 405,
        "message": "The HTTP method is not allowed for this endpoint"
    }
    return jsonify(response), 405
    

def main():
    # Reads FLASK_DEBUG environment variable, defaults to False
    debug_mode = os.getenv("FLASK_DEBUG", "0") in ("1", "true", "True")
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)

if __name__=="__main__":
    main()