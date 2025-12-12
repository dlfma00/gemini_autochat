import streamlit as st
import google.generativeai as genai
import sys
import re 
import os
import time 
import uuid 
import json 

# ===================================================
# ⭐️ 0. CSS 스타일 및 공유 로그 관리 함수
# ===================================================

# 🚨 CSS 정의: 사용자(user) 말풍선 색상을 노란색 계열로 변경
CUSTOM_CSS = """
<style>
/* Streamlit 기본 채팅 메시지 컨테이너 */
.stChatMessage {
    padding: 10px;
    border-radius: 10px;
    margin-bottom: 10px;
}
/* 사용자(role="user") 말풍선에만 노란색 스타일 적용 */
/* data-user="true"는 사용자가 직접 입력한 메시지에만 붙는 속성 */
div[data-testid="stChatMessage"][data-state="final"][data-user="true"] {
    background-color: #fffbdf; /* 연한 노란색 */
    border-left: 5px solid #ffcc00; /* 왼쪽에 강조선을 추가 */
}
</style>
"""

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
            json.dump(messages, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"채팅 로그 저장 중 오류 발생: {e}")

# 🚨 새 채팅 시작 시 파일 내용도 초기화하는 함수
def initialize_shared_log():
    save_chat_log([])


# ===================================================
# ⭐️ 1. 파싱 함수 정의 (캐릭터별 말풍선 분리)
# 
# 🚨🚨🚨 수정됨: 이 함수는 이제 출력을 하지 않고, 저장할 메시지 리스트만 반환합니다.
# ===================================================

def parse_and_display_response(response_text):
    """
    Gemini 응답 텍스트를 [이름]: 대사 형식으로 분리하고 저장할 메시지 리스트를 반환합니다.
    """
    pattern = re.compile(r'\n*(\[[^\]]+\]:\s*)') 
    
    parts = pattern.split(response_text)
    
    messages_to_save = []
    
    for i in range(1, len(parts), 2):
        speaker = parts[i].strip() # [강건우]:
        dialogue = parts[i+1].strip() # 대화 내용
        
        if dialogue: 
            # 🚨 출력 로직 및 time.sleep(1) 제거 🚨
            # 모든 출력은 st.rerun() 이후에 통합된 로그를 통해 이루어집니다.
            messages_to_save.append({"role": "assistant", "content": f"**{speaker}** {dialogue}"})
            
    return messages_to_save

# ===================================================
# ⭐️ 2. 파일 로드 및 프롬프트 생성 (안정성 강화)
# ===================================================

@st.cache_resource 
def get_system_prompt():
    CHARACTER_FILE_PATH = os.path.join(os.getcwd(), 'characters.txt')
    try:
        # ⚠️ 'characters.txt' 파일이 현재 디렉토리에 있는지 확인하세요.
        with open(CHARACTER_FILE_PATH, 'r', encoding='utf-8') as f:
            CHARACTERS = f.read()
    except FileNotFoundError:
        st.error(f"캐릭터 설정 파일 'characters.txt'를 찾을 수 없습니다. 경로를 확인해주세요: {CHARACTER_FILE_PATH}")
        st.stop()
    except Exception as e:
        st.error(f"캐릭터 설정 파일 로드 오류: {e}")
        st.stop()
        
    return CHARACTERS

# ===================================================
# ⭐️ 3. 모델 초기화 함수 (API 호출 최적화 및 세션 분리)
# ===================================================

@st.cache_resource 
def initialize_model(user_role, unique_uuid): 
    try:
        # secrets.toml 파일에 [secrets] 섹션 아래에 GEMINI_API_KEY가 설정되어 있어야 합니다.
        API_KEY = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        st.error("오류: Gemini API 키(GEMINI_API_KEY)가 Streamlit Secrets에 설정되지 않았습니다.")
        st.stop()
        
    genai.configure(api_key=API_KEY)
    
    CHARACTERS = get_system_prompt()
    
    # 프롬프트 구성 (가독성 유지)
    system_prompt = f"""
    [규칙]: 당신은 아래 6명의 캐릭터를 동시에 연기합니다. 사용자 역할에 맞게 자연스럽게 1~6명이 대화에 참여하세요. 한 사람이 여러 번 말할 수도 있습니다.
    각 캐릭터의 대사는 띄어쓰기 포함 최대 15자를 넘지 않도록 합니다.** (단, ㅋㅋㅋㅋㅋㅋㅋㅋㅋ 등 감정표현이 길어지는 경우나, 말을 길게 해야 할 맥락이 명확한 경우에만 예외적으로 10자를 초과할 수 있습니다.)
    
    [대화 스타일 - 최우선 규칙]: 모든 대사는 **카톡, 트위터, SNS에서 친구끼리 대화하듯** 극도로 비격식적이고 구어체로 작성되어야 합니다.
    1. 문장부호, 띄어쓰기, 조사는 **의도적으로 생략하거나 축약**해야 합니다. 강조합니다. 문장 끝에 점을 찍지 마세요.
    2. 축약어(줄임말), 초성('ㅇㅋ', 'ㄱㄱ'), 밈, 이모티콘('ㅋㅋ', 'ㅠㅠ', 'ㅇㅈ')을 **적극적으로** 사용하세요.
    3. 필요시 급하게 타이핑한 듯한 **오타나 짤막한 감탄사**('아', '헐', '뭐야')가 포함될 수 있습니다.
    4. 종종 사용자가 입력한 말과 관계없이 **자발적으로 대화 주제를 꺼내거나** 기존 맥락과 관계없는 **일상적인 잡담**을 시작하세요.
        **예시 주제:** "이제 뭐하지", "아 배고파", "근데니네 국어숙제 함?", "부장 내일 우리 모여?", "야", "자 게임을 시작한다", "아 시끄러워", "나이제자러감ㅃㅃ"      
        특히, **사용자가 별 뜻이 없는 말을 했을 때는 4명 이상 반응하지 말고** 대화 주제를 전환하세요. 
        절대 **사용자만 의식하지 않고** **주로 본인들끼리 대화**하세요.
    5. 서로를 **적극적으로 비난**하세요. 물타기 하세요. 꼬투리를 잡아 헐뜯으세요. 서로를 의심하고 힐난하세요.
    
    [출력 형식]: 반드시 "[이름]: 대사"로만 작성합니다. (지문 금지)

    [캐릭터 명단]: 
    {CHARACTERS}
    [사용자(User) 설정]: 사용자는 **'{user_role}'입니다.
    """
    
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt
    )
    # history는 비워두고 start_chat으로 새 채팅 세션 시작
    return model.start_chat(history=[])

# ===================================================
# ⭐️ 4. 웹 인터페이스 (UI) 구현 및 로직
# ===================================================

# 🚨 CSS 스타일을 앱에 주입하여 사용자 말풍선 색상을 변경
st.markdown(CUSTOM_CSS, unsafe_allow_html=True) 

st.set_page_config(page_title="괴동챗봇(아직미완성)", layout="wide")
st.title("괴동챗봇(아직미완성)")

if 'user_role' not in st.session_state:
    st.session_state.user_role = ""
    # messages 세션 상태는 사용하지 않고 파일 로그만 사용하도록 변경했습니다.
    # if 'messages' not in st.session_state:
    #      st.session_state.messages = []

# 1. 사용자 역할/이름 입력 UI (사이드바)
user_role_input = st.sidebar.text_input("당신의 이름을 입력하세요:")


# 2. 세션 초기화 및 새 채팅 시작 버튼
if 'chat' not in st.session_state or st.sidebar.button("새 채팅 시작", key="restart_chat_btn"): 
    if user_role_input:
        initialize_shared_log()
        
        # 파일 로그를 세션 상태에 저장하지 않고, 필요할 때마다 로드하도록 유지
        st.session_state.user_role = user_role_input 
        
        unique_session_id = str(uuid.uuid4())
        
        # 모델 재초기화
        st.session_state.chat = initialize_model(st.session_state.user_role, unique_session_id)
        
        st.session_state.initial_message_sent = False
        st.sidebar.success(f"✅ 당신은 [{st.session_state.user_role}]로 입장합니다.")
        
        # 새 채팅 시작 후 즉시 UI 업데이트를 위해 rerun
        st.rerun()
    else:
        st.sidebar.warning("이름을 먼저 입력하고 '새 채팅 시작' 버튼을 눌러주세요.")
    
# 3. 대화 기록 표시 및 입장 메시지 전송
if 'chat' in st.session_state:
    current_log = load_chat_log() 
    
    # 🚨🚨🚨 이 루프가 모든 대화 출력을 담당합니다. 🚨🚨🚨
    # 파일 로그를 기반으로 대화 기록 표시
    for message in current_log:
        # role에 따라 CSS가 구분됩니다.
        if message["role"] == "assistant":
             with st.chat_message("assistant"):
                 # content는 이미 마크다운 형식(예: **[이름]**: 대화)으로 저장되어 있습니다.
                 st.markdown(message["content"])
        else:
             with st.chat_message("user"): # CSS 적용을 위해 role을 "user"로 설정
                 st.markdown(message["content"])
            
    # 입장 메시지 자동 전송 (최초 1회)
    if not st.session_state.initial_message_sent:
        
        initial_input = f"(시스템 알림: '{st.session_state.user_role}'님이 입장하셨습니다.)" 
        user_display_input = f"**[{st.session_state.user_role}]**: (입장)"
        
        # 입장 메시지(사용자 역할)를 로그에 먼저 추가
        current_log.append({"role": "user", "content": user_display_input})
        
        with st.spinner('캐릭터들이 당신의 입장을 인식 중...'):
            try:
                response = st.session_state.chat.send_message(initial_input)
                
                # 1. AI 응답 파싱 (출력 없이 메시지 리스트만 반환)
                parsed_messages = parse_and_display_response(response.text)
                
                # 2. 로그에 AI 응답 추가
                new_log = current_log + parsed_messages
                
                # 3. 파일 로그에 저장
                save_chat_log(new_log)

                # 4. 세션 상태 업데이트 후 재실행 (출력을 위해 스크립트 재실행)
                st.session_state.initial_message_sent = True
                st.rerun() 
                    
            except Exception as e:
                st.error(f"API 호출 중 오류 발생: {e}")
                # 오류 발생 시 시스템 중지
                st.stop() 

# ===================================================
# ⭐️ 5. 사용자 입력 처리 (파일의 가장 아래에 위치)
# ===================================================

if prompt := st.chat_input("채팅을 입력하세요..."):
    
    if 'chat' not in st.session_state:
        st.warning("먼저 이름을 입력하고 '새 채팅 시작' 버튼을 눌러주세요.")
        # 입력 후 경고 메시지를 띄우고 중지
        st.stop()
        
    # 1. 사용자 메시지 포맷팅 및 즉시 출력 
    user_display_prompt = f"**[{st.session_state.user_role}]**: {prompt}"
    # 🚨 이 부분은 rerun 전에 사용자 메시지를 즉시 보여줍니다.
    st.chat_message("user").markdown(user_display_prompt)

    # 2. 전체 로그를 파일에서 읽어와서 사용자 메시지 추가
    updated_messages = load_chat_log()
    updated_messages.append({"role": "user", "content": user_display_prompt})
    
    # 3. Gemini API 호출 및 전체 후속 로직 (try 블록 내부)
    with st.spinner('캐릭터들이 대화 중...'):
        try:
            # API 호출
            response = st.session_state.chat.send_message(prompt) 
            full_response_text = response.text 
            # 🚨🚨🚨 임시 디버깅 코드 🚨🚨🚨
            # 1. API 응답 텍스트 확인
            st.info("API 응답 텍스트 (Raw Response):")
            st.code(full_response_text)
            
            # 2. 파싱 시도
            parsed_messages = parse_and_display_response(full_response_text)
            
            # 3. 파싱 결과 확인
            st.info(f"파싱된 메시지 수: {len(parsed_messages)}")
            # 🚨🚨🚨 임시 디버깅 코드 끝 🚨🚨🚨
            
            updated_messages.extend(parsed_messages)
            
            # 5. 모든 메시지를 파일에 최종 저장
            save_chat_log(updated_messages) 

            # 6. 앱 재실행(Rerun)하여 섹션 3이 새 기록을 로드하고 출력하게 합니다.
            st.rerun() 
            
        except Exception as e:
            # API 호출이 실패하면 오류 메시지 출력
            st.error(f"API 호출 중 오류 발생: {e}")
            st.stop()
