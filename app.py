import streamlit as st
import google.generativeai as genai
import sys
import re # 파싱(분리)을 위해 re 모듈 사용
import os
import time # 세션 분리를 위해 time 모듈 사용

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

            time.sleep(2) # 🚨 2초 지연 유지
            with st.chat_message("assistant"):
                st.markdown(f"**{speaker}** {dialogue}") 
            
            messages_to_save.append({"role": "assistant", "content": f"**{speaker}** {dialogue}"})
            
    # API 요청 최적화: 입장 메시지 처리 후 재실행은 여기서 처리
    if is_initial:
        st.session_state.messages.extend(messages_to_save)
        st.session_state.initial_message_sent = True
        st.rerun() 

    return messages_to_save

# ===================================================
# ⭐️ 2. 파일 로드 및 프롬프트 생성 (안정성 강화)
# ===================================================

# 🚨 파일 로드 및 프롬프트 생성을 최상위 캐시 레이어에서 처리
@st.cache_resource 
def get_system_prompt():
    CHARACTER_FILE_PATH = os.path.join(os.getcwd(), 'characters.txt')
    try:
        with open(CHARACTER_FILE_PATH, 'r', encoding='utf-8') as f:
            CHARACTERS = f.read()
    except Exception as e:
        # 파일 로드 실패 시, 앱을 멈추고 오류 메시지를 표시합니다.
        st.error(f"캐릭터 설정 파일 로드 오류: {e}")
        st.stop()
        
    return CHARACTERS

# ===================================================
# ⭐️ 3. 모델 초기화 함수 (API 호출 최적화)
# ===================================================

# API 호출을 최소화하기 위해 @st.cache_resource 사용
@st.cache_resource 
def initialize_model(user_role, session_id): # 세션 분리 위해 session_id 인자 사용
    # ⚠️ 보안된 API 키 로드 (Streamlit Secrets 사용)
    try:
        API_KEY = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        st.error("오류: Gemini API 키(GEMINI_API_KEY)가 Streamlit Secrets에 설정되지 않았습니다.")
        st.stop()
        
    genai.configure(api_key=API_KEY)
    
    # 캐시된 캐릭터 설정을 가져옵니다.
    CHARACTERS = get_system_prompt()
    
    system_prompt = f"""
    [규칙]: 당신은 아래 6명의 캐릭터를 동시에 연기합니다. 사용자 역할에 맞게 자연스럽게 1~6명이 대화에 참여하세요. 한 사람이 여러 번 말할 수도 있습니다.
    각 캐릭터의 대사는 띄어쓰기 포함 최대 15자를 넘지 않도록 합니다.** (단, ㅋㅋㅋㅋㅋㅋㅋㅋㅋ 등 감정표현이 길어지는 경우나, 말을 길게 해야 할 맥락이 명확한 경우에만 예외적으로 10자를 초과할 수 있습니다.)
    
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
    # 채팅 세션을 항상 빈 기록으로 시작합니다.
    return model.start_chat(history=[])

# ===================================================
# ⭐️ 4. 웹 인터페이스 (UI) 구현 및 로직
# ===================================================

# 🚨 앱 제목을 '괴동챗봇(아직미완성)'으로 유지합니다.
st.set_page_config(page_title="괴동챗봇(아직미완성)", layout="wide")
st.title("괴동챗봇(아직미완성)")

# 🚨 최상위에서 messages 리스트가 없으면 강제 초기화 (세션 공유 방지)
if 'messages' not in st.session_state:
    st.session_state.messages = []

# 1. 사용자 역할 선택 UI (사이드바) -> 🚨 이름 입력으로 대체
user_role = st.sidebar.text_input("당신의 이름을 입력하세요:")


# 2. 세션 초기화 및 새 채팅 시작 버튼
if 'chat' not in st.session_state or st.sidebar.button("새 채팅 시작", key="restart_chat_btn"): 
    if user_role:
        st.session_state.messages = []
        
        # 새로운 세션 ID를 생성하여 캐시 분리 강제 (멀티유저 분리)
        unique_session_id = time.time()
        
        st.session_state.chat = initialize_model(user_role, unique_session_id)
        
        st.session_state.initial_message_sent = False
        # 🚨 역할 대신 입력한 이름을 그대로 사용
        st.sidebar.success(f"✅ 당신은 [{user_role}]로 입장합니다.")
    else:
        st.sidebar.warning("이름을 먼저 입력해 주세요.")
    
# 3. 대화 기록 표시 및 입장 메시지 전송
if 'chat' in st.session_state:
    # 대화 기록 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 입장 메시지 자동 전송 (최초 1회)
    if not st.session_state.initial_message_sent:
        initial_input = f"(시스템 알림: '{user_role}'님이 입장하셨습니다.)"
        with st.spinner('캐릭터들이 당신의 입장을 인식 중...'):
            try:
                response = st.session_state.chat.send_message(initial_input)
                
                st.session_state.messages.append({"role": "user", "content": initial_input})
                
                # 파싱 함수를 통해 입장 메시지 저장 및 출력 후 st.rerun() 호출
                parse_and_display_response(response.text, is_initial=True) 
                
            except Exception as e:
                st.error(f"API 호출 중 오류 발생: {e}")
                st.stop()

# 4. 사용자 입력 처리 (입력창이 항상 보이도록 조건문 밖, 파일의 가장 아래에 위치)
if prompt := st.chat_input("채팅을 입력하세요..."):
    
    # 채팅 객체가 없으면 입력 처리를 중단합니다. (초기화 전 입력 방지)
    if 'chat' not in st.session_state:
        st.warning("먼저 이름을 입력하고 '새 채팅 시작' 버튼을 눌러주세요.")
        st.stop()
        
    # 사용자 메시지 저장
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Gemini API 호출 및 응답
    with st.spinner('캐릭터들이 대화 중...'):
        try:
            response = st.session_state.chat.send_message(prompt)
            full_response_text = response.text 
        except Exception as e:
            st.error(f"API 호출 중 오류 발생: {e}")
            st.stop()
    
    # 응답 파싱 및 저장
    parsed_messages = parse_and_display_response(full_response_text)
    st.session_state.messages.extend(parsed_messages)
