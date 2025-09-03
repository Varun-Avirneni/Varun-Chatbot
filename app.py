from flask import Flask, request, jsonify, render_template
from groq import Groq
import json
import uuid
from datetime import datetime
import os

app = Flask(__name__)

# Initialize Groq client
client = Groq(api_key="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")

# Global storage for all chats
all_chats = {}  # {chat_id: chat_data}
current_chat_id = None

# Persistent user profile (across all chats)
global_user_profile = {
    "name": None,
    "preferences": {},
    "important_facts": []
}

def create_new_chat():
    """Create a new chat session"""
    chat_id = str(uuid.uuid4())[:8]  # Short ID for display
    
    chat_data = {
        "id": chat_id,
        "title": "New Chat",
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "messages": [],
        "working_conversation": [],  # For API calls
        "message_count": 0
    }
    
    all_chats[chat_id] = chat_data
    return chat_id

def generate_chat_title(messages):
    """Generate a title based on first message"""
    if len(messages) >= 1:
        user_msg = messages[0].get("content", "")
        if len(user_msg) > 50:
            return user_msg[:47] + "..."
        return user_msg
    return "New Chat"

def save_chats_to_file():
    """Save all chats to persistent storage"""
    try:
        os.makedirs("saved_chats", exist_ok=True)
        
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "global_user_profile": global_user_profile,
            "all_chats": all_chats,
            "current_chat_id": current_chat_id
        }
        
        with open("saved_chats/all_chats.json", 'w') as f:
            json.dump(export_data, f, indent=2)
            
        return True
    except Exception as e:
        print(f"Error saving chats: {e}")
        return False

def load_chats_from_file():
    """Load chats from persistent storage"""
    global all_chats, current_chat_id, global_user_profile
    
    try:
        if os.path.exists("saved_chats/all_chats.json"):
            with open("saved_chats/all_chats.json", 'r') as f:
                data = json.load(f)
                
            all_chats = data.get("all_chats", {})
            current_chat_id = data.get("current_chat_id")
            global_user_profile = data.get("global_user_profile", {
                "name": None,
                "preferences": {},
                "important_facts": []
            })
            
            print(f"Loaded {len(all_chats)} chats from storage")
            return True
    except Exception as e:
        print(f"Error loading chats: {e}")
    
    return False

def extract_user_info(user_message):
    """Extract important information about the user"""
    global global_user_profile
    
    # Extract name
    user_lower = user_message.lower()
    if ("my name is" in user_lower or "i'm" in user_lower or "i am" in user_lower) and not global_user_profile["name"]:
        words = user_message.split()
        for i, word in enumerate(words):
            if word.lower() in ["is", "am", "i'm"] and i + 1 < len(words):
                potential_name = words[i + 1].strip(".,!?")
                if potential_name.isalpha() and len(potential_name) > 1:
                    global_user_profile["name"] = potential_name
                    global_user_profile["important_facts"].append(f"User's name is {potential_name}")
                    print(f"Learned user's name: {potential_name}")
                    break

def create_enhanced_system_prompt():
    """Create system prompt with user's persistent information"""
    base_prompt = """You are a helpful AI assistant with memory. Key instructions:

RESPONSE STYLE:
- Keep responses SHORT (1-2 sentences, under 40 words)
- Be conversational and natural for voice
- Reference previous conversation context when relevant

MEMORY USAGE:"""
    
    if global_user_profile["name"]:
        base_prompt += f"\n- User's name is {global_user_profile['name']} - USE IT naturally in conversation"
    
    if global_user_profile["important_facts"]:
        base_prompt += f"\n- Important facts about user: {'; '.join(global_user_profile['important_facts'][-3:])}"
    
    base_prompt += "\n\nRemember and reference these details throughout our conversation."
    
    return base_prompt

# Load chats on startup
print("Starting Flask application...")
load_chats_from_file()

# Create initial chat if none exists
if not all_chats:
    current_chat_id = create_new_chat()
    print("Created initial chat")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/new_chat", methods=["POST"])
def new_chat():
    """Create a new chat session"""
    global current_chat_id
    
    # Auto-save current chat before switching
    save_chats_to_file()
    
    # Create new chat
    new_chat_id = create_new_chat()
    current_chat_id = new_chat_id
    
    print(f"Created new chat: {new_chat_id}")
    
    return jsonify({
        "status": "success",
        "chat_id": new_chat_id,
        "message": "New chat created!"
    })

@app.route("/get_chats", methods=["GET"])
def get_chats():
    """Get list of all chats"""
    chat_list = []
    
    for chat_id, chat_data in all_chats.items():
        chat_list.append({
            "id": chat_id,
            "title": chat_data.get("title", "New Chat"),
            "last_updated": chat_data.get("last_updated", datetime.now().isoformat()),
            "message_count": chat_data.get("message_count", 0),
            "preview": chat_data.get("messages", [{}])[0].get("content", "No messages")[:50] + ("..." if len(chat_data.get("messages", [{}])[0].get("content", "")) > 50 else ""),
            "is_current": chat_id == current_chat_id
        })
    
    # Sort by last updated (most recent first)
    chat_list.sort(key=lambda x: x["last_updated"], reverse=True)
    
    return jsonify({
        "chats": chat_list,
        "current_chat_id": current_chat_id
    })

@app.route("/switch_chat", methods=["POST"])
def switch_chat():
    """Switch to a different chat"""
    global current_chat_id
    
    data = request.get_json()
    chat_id = data.get("chat_id")
    
    if chat_id in all_chats:
        # Save current state before switching
        save_chats_to_file()
        
        current_chat_id = chat_id
        chat_data = all_chats[chat_id]
        
        print(f"Switched to chat: {chat_id}")
        
        return jsonify({
            "status": "success",
            "chat_id": chat_id,
            "messages": chat_data.get("messages", []),
            "title": chat_data.get("title", "New Chat"),
            "message_count": chat_data.get("message_count", 0)
        })
    else:
        return jsonify({"status": "error", "message": "Chat not found"})

@app.route("/delete_chat", methods=["POST"])
def delete_chat():
    """Delete a chat"""
    global current_chat_id, all_chats
    
    data = request.get_json()
    chat_id = data.get("chat_id")
    
    if chat_id in all_chats:
        del all_chats[chat_id]
        print(f"Deleted chat: {chat_id}")
        
        # If deleting current chat, switch to another or create new
        if chat_id == current_chat_id:
            if all_chats:
                current_chat_id = list(all_chats.keys())[0]
            else:
                current_chat_id = create_new_chat()
        
        save_chats_to_file()
        
        return jsonify({
            "status": "success",
            "new_current_chat": current_chat_id
        })
    else:
        return jsonify({"status": "error", "message": "Chat not found"})

@app.route("/ask", methods=["POST"])
def ask():
    global all_chats, current_chat_id, global_user_profile
    
    try:
        data = request.get_json()
        user_message = data.get("message", "").strip()
        
        print(f"User message: {user_message}")
        
        if not user_message:
            return jsonify({"response": "Please say something!"})

        # Ensure we have a current chat
        if not current_chat_id or current_chat_id not in all_chats:
            current_chat_id = create_new_chat()

        current_chat = all_chats[current_chat_id]
        
        # Add user message to current chat
        user_msg_data = {
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        }
        
        current_chat["messages"].append(user_msg_data)
        current_chat["working_conversation"].append({
            "role": "user",
            "content": user_message
        })
        
        # Keep working conversation manageable
        if len(current_chat["working_conversation"]) > 12:
            current_chat["working_conversation"] = current_chat["working_conversation"][-12:]

        # Update chat title if this is first user message
        if len([msg for msg in current_chat["messages"] if msg["role"] == "user"]) == 1:
            current_chat["title"] = generate_chat_title([user_msg_data])

        # Extract user info (global across all chats)
        extract_user_info(user_message)
        
        # Create system prompt
        system_prompt = create_enhanced_system_prompt()
        
        # Prepare messages for API
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(current_chat["working_conversation"])

        print("Sending to Groq...")
        
        # Call Groq API
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=100,
            temperature=0.7
        )

        ai_response = response.choices[0].message.content.strip()
        print(f"AI response: {ai_response}")
        
        # Add AI response to current chat
        ai_msg_data = {
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.now().isoformat()
        }
        
        current_chat["messages"].append(ai_msg_data)
        current_chat["working_conversation"].append({
            "role": "assistant",
            "content": ai_response
        })
        
        # Update chat metadata
        current_chat["last_updated"] = datetime.now().isoformat()
        current_chat["message_count"] = len(current_chat["messages"])
        
        # Auto-save every few messages
        if current_chat["message_count"] % 4 == 0:
            save_chats_to_file()
        
        return jsonify({
            "response": ai_response,
            "user_name": global_user_profile["name"],
            "message_count": current_chat["message_count"],
            "chat_id": current_chat_id,
            "chat_title": current_chat["title"]
        })

    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({"response": f"Error: {str(e)}"})

@app.route("/export_chat", methods=["GET"])
def export_chat():
    """Export current chat"""
    if current_chat_id and current_chat_id in all_chats:
        try:
            os.makedirs("saved_chats", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"saved_chats/chat_{current_chat_id}_{timestamp}.json"
            
            export_data = {
                "chat_id": current_chat_id,
                "title": all_chats[current_chat_id]["title"],
                "exported_at": datetime.now().isoformat(),
                "user_profile": global_user_profile,
                "messages": all_chats[current_chat_id]["messages"]
            }
            
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            return jsonify({
                "status": "success",
                "filename": filename,
                "message_count": len(all_chats[current_chat_id]["messages"])
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    else:
        return jsonify({"status": "error", "message": "No current chat to export"})

@app.route("/get_chat_data", methods=["GET"])
def get_chat_data():
    """Get current chat data for download"""
    if current_chat_id and current_chat_id in all_chats:
        export_data = {
            "chat_id": current_chat_id,
            "title": all_chats[current_chat_id]["title"],
            "export_date": datetime.now().isoformat(),
            "user_profile": global_user_profile,
            "total_messages": len(all_chats[current_chat_id]["messages"]),
            "messages": all_chats[current_chat_id]["messages"]
        }
        return jsonify(export_data)
    else:
        return jsonify({"status": "error", "message": "No current chat"})

@app.route("/get_memory_info", methods=["GET"])
def get_memory_info():
    """Get current memory/profile info"""
    current_chat_messages = 0
    if current_chat_id and current_chat_id in all_chats:
        current_chat_messages = len(all_chats[current_chat_id]["messages"])
    
    total_messages = sum(len(chat.get("messages", [])) for chat in all_chats.values())
    
    return jsonify({
        "user_profile": global_user_profile,
        "current_chat_messages": current_chat_messages,
        "total_messages_all_chats": total_messages,
        "total_chats": len(all_chats),
        "current_chat_id": current_chat_id
    })

if __name__ == "__main__":
    print("Starting Enhanced Flask server with Chat Management...")
    print(f"Loaded {len(all_chats)} existing chats")
    if global_user_profile["name"]:
        print(f"User profile loaded: {global_user_profile['name']}")
    app.run(host="0.0.0.0", port=5000, debug=True)