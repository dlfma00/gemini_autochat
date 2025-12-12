import streamlit as st
import google.generativeai as genai
import sys
import re 
import os
import time 
import uuid 
import json 
from google.generativeai.types import Part

# ===================================================
# ⭐️ 0. CSS 스타일 및 공유 로그 관리 함수 
# ===================================================

CUSTOM_CSS = """
<style>
/* Streamlit 기본 채팅 메시지 컨테이너 */
.stChatMessage {
    padding: 10px;
    border-radius: 10px;
    margin-bottom: 10px;
}
/* 사용자(role="user") 말풍선에만 노란색 스타일 적용 */
div[data-testid="stChatMessage"][data-state="final"][data-user="true"] {
    background-color: #fffbdf; /* 연한 노란색 */
    border-left: 5px solid #ffcc00; /* 왼쪽에 강조선을 추가 */
}
</style>
"""

# ===================================================
# ⭐️ 1-1. 파싱 함수 정의 (캐릭터별 말풍선 분리)
# ===================================================

def parse_and_display_response(response_text):
    """
    Gemini 응답 텍스트를 [이름]: 대사 형식으로 분리하고 저장할 메시지 리스트를 반환합니다.
    """
    # 콜론이나 공백이 있든 없든, 이름 [이름] 다음에 오는 모든 것을 분리 시도
    pattern = re.compile(r'\n*(\[[^\]]+\][ :]*\s*)') 
    
    parts = pattern.split(response_text)
    
    messages_to_save = []
    
    for i in range(1, len(parts), 2):
        speaker = parts[i].strip() # [이름]: (예시 이름 없이 역할만 표시)
        dialogue = parts[i+1].strip() # 대화 내용
        
        if dialogue: 
            messages_to_save.append({"role": "assistant", "content": f"**{speaker}** {dialogue}"})
            
    return messages_to_save

# ===================================================
# ⭐️ 1-2. 히스토리 변환 및 30턴 제한 함수 
# ===================================================

def format_and_truncate_history(messages, max_turns=30):
    """
    Streamlit session messages를 Gemini API Contents list로 변환하고, 
    최대 max_turns만큼만 유지합니다.
    """
    history_to_send = messages[-max_turns:]
    gemini_contents = []
    
    for message in history_to_send:
        role = message["role"]
        content_text = message["content"]
        
        gemini_role = "model" if role == "assistant" else "user"
        
        # API에 전달할 때는 Streamlit 출력용 마크다운 포맷(**[이름]:**)을 제거해야 합니다.
        clean_text = re.sub(r'\*\*\[[^\]]+\]\*\*[:\s]*', '', content_text, 1).strip()
            
        if clean_text:
             gemini_contents.append({"role": gemini_role, "parts": [clean_text]})

    return gemini_contents

# ===================================================
# ⭐️ 2. 파일 로드 및 프롬프트 생성
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
# ⭐️ 3. 모델 초기화 함수
# ===================================================

def initialize_model(user_role): 
    try:
        API_KEY = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        st.error("오류: Gemini API 키(GEMINI_API_KEY)가 Streamlit Secrets에 설정되지 않았습니다.")
        st.stop()
        
    genai.configure(api_key=API_KEY) 
    
    CHARACTERS = get_system_prompt()
    
    # 🚨 CHARACTERS 변수를 사용하여 시스템 프롬프트 구성 (캐릭터 이름 하드코딩 없음) 🚨
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
    return model

# ===================================================
# ⭐️ 4. 웹 인터페이스 (UI) 구현 및 로직
# ===================================================

st.markdown(CUSTOM_CSS, unsafe_allow_html=True) 

st.set_page_config(page_title="괴동챗봇(아직미완성)", layout="wide")
st.title("괴동챗봇(아직미완성)")

# 🚨 AttributeError 해결을 위한 최상위 세션 상태 초기화
if 'user_role' not in st.session_state:
    st.session_state.user_role = ""

if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'model' not in st.session_state: 
    st.session_state.model = None
# -------------------------------------------------------------

# 1. 사용자 역할/이름 입력 UI (사이드바)
user_role_input = st.sidebar.text_input("당신의 이름을 입력하세요:")


# 2. 세션 초기화 및 새 채팅 시작 버튼 (GenerativeModel 객체 생성 및 세션 상태 초기화)
if st.session_state.model is None or st.sidebar.button("새 채팅 시작", key="restart_chat_btn"): 
    if user_role_input:
        
        st.session_state.messages = [] # 대화 기록 초기화 (사용자별)
        st.session_state.user_role = user_role_input 
        
        # Model 객체를 생성하여 세션 상태에 저장합니다.
        st.session_state.model = initialize_model(st.session_state.user_role)
        
        st.session_state.initial_message_sent = False
        st.sidebar.success(f"✅ 당신은 [{st.session_state.user_role}]로 입장합니다.")
        
        st.rerun()
    else:
        st.sidebar.warning("이름을 먼저 입력하고 '새 채팅 시작' 버튼을 눌러주세요.")


# 3. 대화 기록 표시 및 입장 메시지 전송
if st.session_state.model is not None: # model이 생성된 후에만 실행
    
    # 세션 상태 메시지를 기반으로 대화 기록 표시
    for message in st.session_state.messages:
        # role에 따라 CSS가 구분됩니다.
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
    # 입장 메시지 자동 전송 (최초 1회)
    if not st.session_state.initial_message_sent:
        
        initial_input = f"(시스템 알림: '{st.session_state.user_role}'님이 입장하셨습니다.)" 
        user_display_input = f"**[{st.session_state.user_role}]**: (입장)"
        
        # 1. 입장 메시지(사용자 역할)를 세션 상태에 추가
        st.session_state.messages.append({"role": "user", "content": user_display_input})
        
        with st.spinner('캐릭터들이 당신의 입장을 인식 중...'):
            try:
                # 2. 히스토리 구성 (입장 메시지 1개 포함)
                contents = format_and_truncate_history(st.session_state.messages, max_turns=30)
                
                # 3. API 호출 (generate_content 사용)
                # 모델이 이전 대화(히스토리)를 기반으로 다음 응답을 생성하도록 합니다.
                response = st.session_state.model.generate_content(contents)
                
                # 4. AI 응답 파싱 및 로그에 추가
                parsed_messages = parse_and_display_response(response.text)
                st.session_state.messages.extend(parsed_messages)
                
                # 5. 세션 상태 업데이트 후 재실행
                st.session_state.initial_message_sent = True
                st.rerun() 
                    
            except Exception as e:
                st.error(f"API 호출 중 오류 발생: {e}")
                st.stop() 

# ===================================================
# ⭐️ 5. 사용자 입력 처리 
# ===================================================

if prompt := st.chat_input("채팅을 입력하세요..."):
    
    if st.session_state.model is None:
        st.warning("먼저 이름을 입력하고 '새 채팅 시작' 버튼을 눌러주세요.")
        st.stop()
        
    # 1. 사용자 메시지 포맷팅 및 즉시 출력 
    user_display_prompt = f"**[{st.session_state.user_role}]**: {prompt}"
    st.chat_message("user").markdown(user_display_prompt)

    # 2. 사용자 메시지를 세션 상태에 추가
    st.session_state.messages.append({"role": "user", "content": user_display_prompt})
    
    # 3. Gemini API 호출 및 전체 후속 로직 (try 블록 내부)
    with st.spinner('캐릭터들이 대화 중...'):
        try:
            # 🚨🚨🚨 히스토리(30턴 제한)를 Contents로 변환 🚨🚨🚨
            contents = format_and_truncate_history(st.session_state.messages, max_turns=30)

            # API 호출 (generate_content 사용, history 포함)
            response = st.session_state.model.generate_content(contents) 
            full_response_text = response.text 
            
            # 4. AI 응답 파싱 및 로그에 추가
            parsed_messages = parse_and_display_response(full_response_text)
            
            # 세션 상태에 직접 추가
            st.session_state.messages.extend(parsed_messages)
            
            # 5. 앱 재실행(Rerun)하여 새 기록을 출력하게 합니다.
            st.rerun() 
            
        except Exception as e:
            st.error(f"API 호출 중 오류 발생: {e}")
            st.stop()
