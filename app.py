from flask import Flask, request, render_template, jsonify, session
from openai import OpenAI
from dotenv import load_dotenv  #dotenv 불러오기
from uuid import uuid4

from multi_file_parser import extract_texts_from_folder

import json
import os


#환경 변수 로드

load_dotenv()   #.env 파일의 내용을 읽어서 환경 변수로 설정정

app = Flask(__name__)

#.env 파일에서 API 키를 가져옴 (보안을 위해서)
api_key = os.getenv("OPENAI_API_KEY")
app.secret_key = os.getenv("SECRET_KEY")    #.env 파일에서 OPENAI_API_KEY룰 불러옴
client = OpenAI(api_key = api_key) 

# 학습된 자료 불러오기
data_folder = "./data_files"  # 여기에 .pdf, .docx, .pptx 파일을 모아두세요
file_knowledge = extract_texts_from_folder(data_folder)

# 사용자별 대화 기록 저장용 딕셔너리 (서버가 실행되는 동안만 유지)
chat_histories = {}

# 전체 대화 로그 저장 파일
LOG_FILE = "chat_logs.json"

# 대화 로그 파일에 저장
def save_chat_log(session_id, user_message, bot_message):
    log = {
        "session_id": session_id,
        "user": user_message,
        "bot": bot_message,
        "timestamp": str(uuid4())
    }
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    else:
        logs = []
    logs.append(log)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


# 기본 페이지 렌더링
@app.route("/")
def index():
    if "session_id" not in session:
        session["session_id"] = str(uuid4())  # 사용자가 처음 접속하면 고유한 session_id 생성
    return render_template("index.html")

# 질문-응답 API
@app.route("/ask", methods=["POST"])
def ask():
    session_id = session.get("session_id")  # 현재 사용자의 session_id
    user_message = request.json["message"]  # 클라이언트로부터 받은 질문

    # 사용자가 처음 접속한 경우 대화 기록 초기화
    if session_id not in chat_histories:
        chat_histories[session_id] = [{
            "role": "system",
            "content": (
                "너는 메이킹 교육 분야에 특화된 교육용 챗봇 Nasky야.\n"
                "질문은 미리 학습된 문서 자료(.pdf, .docx, .pptx)를 기반으로 답해야 해.\n"
                "다음은 학습된 자료야:\n\n" + file_knowledge + "\n\n"
                "답변 형식:\n"
                "- 문단은 줄바꿈\n"
                "- 목록은 '-' 또는 숫자\n"
                "- 명령어나 코드 블록은 백틱(`) 사용\n"
                "- 항상 개념 설명 → 예시 → 질문 유도로 답변할 것"
            )
          }]
        # "" 안에 내용을 어떻게 구성하냐에 따라 챗봇의 답변을 유도할 수 있다.
                                                                                
    # 사용자 메시지를 대화 기록에 추가
    chat_histories[session_id].append({"role": "user", "content": user_message})

    # OpenAI API로 대답 생성
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=chat_histories[session_id],  # 이전 대화 기록도 포함하여 요청
        temperature=0.7
    )

    reply = response.choices[0].message.content  # 챗봇의 응답을 가져옴

    # 응답을 대화 기록에 추가
    chat_histories[session_id].append({"role": "assistant", "content": reply})

    # 대화 로그 저장
    save_chat_log(session_id, user_message, reply)

    # JSON 형식으로 응답 반환
    return jsonify({"reply": reply})

@app.route("/history")
def history():
    session_id = session.get("session_id")  # 현재 세션의 ID 가져오기
    if session_id in chat_histories:
        return render_template("history.html", chat_histories=chat_histories[session_id])
    else:
        return "대화 기록이 없습니다.", 404


# 관리자용 전체 로그 보기
@app.route("/admin")
def admin():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    else:
        logs = []
    return render_template("admin.html", all_histories=chat_histories)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
