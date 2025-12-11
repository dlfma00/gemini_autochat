import streamlit as st
import google.generativeai as genai
import sys
import re 
import os
import time 
import uuid 
import json # 🚨 JSON 모듈 추가: 채팅 로그 저장/로드를 위해 사용

# ===================================================
# ⭐️ 0. 공유 로그 관리 함수
# ===================================================
CHAT_LOG_FILE = "chat_log.json"

# 🚨 채팅 기록을 파일에서 읽어오는 함수
def load_chat_log():
    try:
        if os.path.exists(CHAT_LOG_FILE):
            with open(CHAT_LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        # 파일이 비어있거나 깨졌을 경우 빈 리스트 반환
        return []
    return []

# 🚨 채팅 기록을 파일에 저장하는 함수
def save_chat_log(messages):
    try:
        with open(CHAT_LOG_FILE, 'w', encoding='utf-8') as f:
            # ensure_ascii=False로 한글 깨짐 방지
            json.dump(messages, f, ensure_ascii=False, indent=4)
    except Exception as e:
        # Streamlit Cloud에서는 파일 쓰기 권한 오류가 발생할 수 있습니다.
        st.error(f"채팅 로그 저장 중 오류 발생: {e}")

# 🚨 새 채팅 시작 시 파일 내용도 초기화하는 함수
def initialize_shared_log():
    # 빈 리스트를 파일에 저장하여 로그를 초기화
    save_chat_log([])


# ===================================================
# ⭐️ 1. 파싱 함수 정의 (캐릭터별 말풍선 분리)
# ===================================================

# Gemini 응답 텍스트를 [이름]: 대사 형식으로 분리하고 출력하는 함수
def parse_and_display_response(response_text, is_initial=False):
    # 정규식: 대괄호 안의 이름과 콜론을 찾음 (예: [강건우]:)
    pattern = re.compile(r'\n*(\[[^\]]+\]:\s*)') 
    
    parts = pattern.split(response_text)
    
    messages_to_save = []
    
    for i in range(1, len(parts), 2):
        speaker = parts[i].strip() # [강건우]:
        dialogue = parts[i+1].strip() # 대화 내용
        
        if dialogue: 

            # 🚨 출력 시 1초 지연 추가 (현실감 부여)
            time.sleep(1) 
            with st.chat_message("assistant"):
                st.markdown(f"**{speaker}** {dialogue}") 
            
            messages_to_save.append({"role": "assistant", "content": f"**{speaker}** {dialogue}"})
            
    # 입장 메시지 처리 후 재실행 로직
    if is_initial:
        # 🚨 입장 메시지는 일단 세션 상태에 저장 후 st.rerun()으로 재시작하여 파일 로드 로직을 다시 타도록 합니다.
        st.session_state.messages.extend(messages_to_save)
        st.session_state.initial_message_sent = True
        st.rerun() 

    return messages_to_save

# ===================================================
# ⭐️ 2. 파일 로드 및 프롬프트 생성 (안정성 강화)
# ===================================================

@st.cache_resource 
def get_system_prompt():
    CHARACTER_FILE_PATH = os.path.join(os.getcwd(), 'characters.txt')
    try:
        with open(CHARACTER_FILE_PATH, 'r', encoding='utf-8') as f:
            CHARACTERS = f.read()
    except Exception as e:
        st.error(f"캐릭터 설정 파일 로드 오류: {e}")
        st.stop()
        
    return CHARACTERS

# ===================================================
# ⭐️ 3. 모델 초기화 함수 (API 호출 최적화 및 세션 분리)
# ===================================================

# API 호출을 최소화하기 위해 @st.cache_resource 사용
@st.cache_resource 
def initialize_model(user_role, unique_uuid): # 🚨 uuid_key를 캐시 무효화 인자로 사용
    # ⚠️ 보안된 API 키 로드 (Streamlit Secrets 사용)
    try:
        API_KEY = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        st.error("오류: Gemini API 키(GEMINI_API_KEY)가 Streamlit Secrets에 설정되지 않았습니다.")
        st.stop()
        
    genai.configure(api_key=API_KEY)
    
    CHARACTERS = get_system_prompt()
    
    system_prompt = f"""
    [규칙]: 당신은 아래 6명의 캐릭터를 동시에 연기합니다. 사용자 역할에 맞게 자연스럽게 1~6명이 대화에 참여하세요. 한 사람이 여러 번 말할 수도 있습니다.
    각 캐릭터의 대사는 띄어쓰기 포함 최대 15자를 넘지 않도록 합니다.** (단, ㅋㅋㅋㅋㅋㅋㅋㅋㅋ 등 감정표현이 길어지는 경우나, 말을 길게 해야 할 맥락이 명확한 경우에만 예외적으로 10자를 초과할 수 있습니다.)
    
    [자발적 대화 규칙]:
    1.  사용자가 입력하지 않더라도, **자발적으로 대화 주제를 꺼내거나** 기존 맥락과 관계없는 **일상적인 잡담**을 시작할 수 있습니다.
    2.  **예시 주제:** "배고파", "오늘 숙제 했냐?", "내일 모임 몇 시?", "뭐 재밌는 일 없음?" 등 고등학생들이 나눌법한 일상적인 대화를 자유롭게 던지세요.

    [대화 스타일 - 최우선 규칙]: 모든 대사는 **카톡, 트위터, SNS에서 친구끼리 대화하듯** 극도로 비격식적이고 구어체로 작성되어야 합니다.
    1. 문장부호, 띄어쓰기, 조사는 **의도적으로 생략하거나 축약**해야 합니다. 강조합니다. 문장 끝에 점을 찍지 마세요.
    2. 축약어(줄임말), 초성('ㅇㅋ', 'ㄱㄱ'), 밈, 이모티콘('ㅋㅋ', 'ㅠㅠ', 'ㅇㅈ')을 **적극적으로** 사용하세요.
    3. 필요시 급하게 타이핑한 듯한 **오타나 짤막한 감탄사**('아', '헐', '뭐야')가 포함될 수 있습니다.
    4. 종종 사용자가 입력한 말과 관계없이 **자발적으로 대화 주제를 꺼내거나** 기존 맥락과 관계없는 **일상적인 잡담**을 시작하세요.
        **예시 주제:** "아 배고파", "근데니네 국어숙제 함?", "부장 내일 우리 모여?"
        특히, **사용자가 별 뜻이 없는 말을 했을 때는 4명 이상 반응하지 말고** 대화 주제를 전환하세요. 
        절대 **사용자만 의식하지 않고** **주로 본인들끼리 대화**하세요.
    5. 서로를 **적극적으로 비난**하세요. 물타기 하세요. 
    
    [출력 형식]: 반드시 "[이름]: 대사"로만 작성합니다. (지문 금지)

    [캐릭터 명단]: 
    {CHARACTERS}
    [사용자(User) 설정]: 사용자는 **'{user_role}'입니다.
    """
    
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt
    )
    return model.start_chat(history=[])

# ===================================================
# ⭐️ 4. 웹 인터페이스 (UI) 구현 및 로직
# ===================================================

st.set_page_config(page_title="괴동챗봇(아직미완성)", layout="wide")
st.title("괴동챗봇(아직미완성)")

# 🚨 최상위에서 user_role 세션 상태가 없으면 초기화
if 'user_role' not in st.session_state:
    st.session_state.user_role = ""
    # 🚨 'messages' 세션 상태는 사용하지 않지만, Streamlit 호환성을 위해 유지
    if 'messages' not in st.session_state:
         st.session_state.messages = []

# 1. 사용자 역할/이름 입력 UI (사이드바)
user_role_input = st.sidebar.text_input("당신의 이름을 입력하세요:")


# 2. 세션 초기화 및 새 채팅 시작 버튼
if 'chat' not in st.session_state or st.sidebar.button("새 채팅 시작", key="restart_chat_btn"): 
    if user_role_input:
        # 🚨 공유 파일 로그 초기화 (새 대화 시작)
        initialize_shared_log()
        
        st.session_state.messages = load_chat_log() # 🚨 파일에서 로드
        st.session_state.user_role = user_role_input # 🚨 현재 사용자 이름을 세션에 저장
        
        # 새로운 세션 ID를 생성하여 캐시 분리 강제 (멀티유저 분리)
        unique_session_id = str(uuid.uuid4())
        
        st.session_state.chat = initialize_model(st.session_state.user_role, unique_session_id)
        
        st.session_state.initial_message_sent = False
        st.sidebar.success(f"✅ 당신은 [{st.session_state.user_role}]로 입장합니다.")
    else:
        st.sidebar.warning("이름을 먼저 입력하고 '새 채팅 시작' 버튼을 눌러주세요.")
    
# 3. 대화 기록 표시 및 입장 메시지 전송
if 'chat' in st.session_state:
    # 🚨 앱이 실행될 때마다 파일에서 최신 기록을 읽어옴
    current_log = load_chat_log() 
    
    # 🚨 파일 로그를 기반으로 대화 기록 표시
    for message in current_log:
        # role은 이제 출력에 중요하지 않으므로, 모두 'user'로 통일하여 처리
        with st.chat_message("user"): 
            st.markdown(message["content"]) 
            
    # 입장 메시지 자동 전송 (최초 1회)
    if not st.session_state.initial_message_sent:
        initial_input = f"(시스템 알림: '{st.session_state.user_role}'님이 입장하셨습니다.)" 
        with st.spinner('캐릭터들이 당신의 입장을 인식 중...'):
            try:
                response = st.session_state.chat.send_message(initial_input)
                
                # 🚨 1. 사용자 메시지 (입장)를 로그에 추가
                user_display_input = f"**[{st.session_state.user_role}]**: (입장)"
                
                # 🚨 2. AI 응답 파싱 및 로그에 추가
                parsed_messages = parse_and_display_response(response.text)
                
                # 🚨 3. 파일 로그에 저장
                new_log = current_log + [{"role": "user", "content": user_display_input}] + parsed_messages
                save_chat_log(new_log)

                # 🚨 4. 세션 상태 업데이트 후 재실행
                st.session_state.initial_message_sent = True
                st.rerun() 
                
            except Exception as e:
                st.error(f"API 호출 중 오류 발생: {e}")
                st.stop()

# 4. 사용자 입력 처리 (입력창이 항상 보이도록 조건문 밖, 파일의 가장 아래에 위치)
if prompt := st.chat_input("채팅을 입력하세요..."):
    
    if 'chat' not in st.session_state:
        st.warning("먼저 이름을 입력하고 '새 채팅 시작' 버튼을 눌러주세요.")
        st.stop()
        
    # 1. 사용자 메시지 포맷팅
    user_display_prompt = f"**[{st.session_state.user_role}]**: {prompt}"
        
    # 2. 전체 로그를 파일에서 읽어와서 사용자 메시지 추가
    updated_messages = load_chat_log()
    updated_messages.append({"role": "user", "content": user_display_prompt})
    
    # 3. Gemini API 호출
    with st.spinner('캐릭터들이 대화 중...'):
        try:
            response = st.session_state.chat.send_message(prompt) 
            full_response_text = response.text 
        except Exception as e:
            st.error(f"API 호출 중 오류 발생: {e}")
            st.stop()
    
    # 4. AI 응답 파싱 및 로그에 추가
    parsed_messages = parse_and_display_response(full_response_text)
    updated_messages.extend(parsed_messages)
    
    # 5. 🚨 모든 메시지를 파일에 최종 저장
    save_chat_log(updated_messages) 

    # 6. 🚨 앱 재실행(Rerun)하여 다른 사용자도 새 기록을 로드하게 유도
    st.rerun()
