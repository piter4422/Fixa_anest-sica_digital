import streamlit as st
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components
import plotly.graph_objects as go
from fpdf import FPDF 
import matplotlib.pyplot as plt
import tempfile
import os
import time

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E MEMÓRIA
# ==========================================
st.set_page_config(page_title="Prontuário Digital Anestesia", page_icon="🩺", layout="wide", initial_sidebar_state="expanded")

if 'historico_vet' not in st.session_state:
    st.session_state.historico_vet = pd.DataFrame(columns=['Hora', 'FC', 'FR', 'PAS', 'SpO2', 'Temp', 'Alertas'])
if 'dados_paciente' not in st.session_state:
    st.session_state.dados_paciente = {
        "nome": "", "id_paciente": "", "raca": "", 
        "peso": 0.0, "especie": "Cão (Pequeno Porte)", "procedimento": "", "asa": "ASA I (Normal/Saudável)"
    }
if 'dados_confirmados' not in st.session_state:
    st.session_state.dados_confirmados = False

# ==========================================
# BANCO DE DADOS CLÍNICO
# ==========================================
LIMITES = {
    "Cão (Pequeno Porte)": {"FC": {"min": 90, "max": 160, "margem": 10}, "FR": {"min": 10, "max": 30, "margem": 5}, "PAS": {"min": 90, "max": 140, "margem": 10}},
    "Cão (Grande Porte)": {"FC": {"min": 60, "max": 100, "margem": 10}, "FR": {"min": 10, "max": 30, "margem": 5}, "PAS": {"min": 90, "max": 140, "margem": 10}},
    "Gato": {"FC": {"min": 120, "max": 200, "margem": 15}, "FR": {"min": 15, "max": 40, "margem": 5}, "PAS": {"min": 90, "max": 140, "margem": 10}}
}

doses_caes = {
    "Adrenalina (Epinefrina)": {"dose": 0.01, "unidade": "mg", "obs": "Parada Cardíaca (0.01 mg/kg)"},
    "Atropina": {"dose": 0.02, "unidade": "mg", "obs": "Bradicardia severa (0.02 mg/kg)"},
    "Noradrenalina": {"dose": 0.1, "unidade": "mcg/min", "obs": "Hipotensão (0.1 mcg/kg/min)"},
    "Lidocaína 2%": {"dose": 2.0, "unidade": "mg", "obs": "Arritmia ventricular (2.0 mg/kg)"}
}

FARMACOS_EMERGENCIA = {
    "Cão (Pequeno Porte)": doses_caes,
    "Cão (Grande Porte)": doses_caes,
    "Gato": {
        "Adrenalina (Epinefrina)": {"dose": 0.01, "unidade": "mg", "obs": "Parada Cardíaca (0.01 mg/kg)"},
        "Atropina": {"dose": 0.02, "unidade": "mg", "obs": "Bradicardia severa (0.02 mg/kg)"},
        "Noradrenalina": {"dose": 0.1, "unidade": "mcg/min", "obs": "Hipotensão (0.1 mcg/kg/min)"},
        "Flumazenil": {"dose": 0.01, "unidade": "mg", "obs": "Reversão BZD (0.01 mg/kg)"}
    }
}

# ==========================================
# FUNÇÕES DE LÓGICA CLÍNICA E PDF
# ==========================================
def avaliar_parametros_completos(fc, fr, pas, spo2, temp, limites):
    alertas = []
    profundo = superficial = 0
    
    if fc < limites["FC"]["min"]: profundo += 1; alertas.append("Bradicardia")
    if fr < limites["FR"]["min"]: profundo += 1; alertas.append("Bradipneia")
    if pas < limites["PAS"]["min"]: profundo += 1; alertas.append("Hipotensão")
    
    if fc > limites["FC"]["max"]: superficial += 1; alertas.append("Taquicardia")
    if fr > limites["FR"]["max"]: superficial += 1; alertas.append("Taquipneia")
    if pas > limites["PAS"]["max"]: superficial += 1; alertas.append("Hipertensão")

    if spo2 < 90: alertas.append("Hipóxia Severa")
    elif spo2 <= 94: alertas.append("Atenção SpO2")
    
    if temp < 36.5: alertas.append("Hipotermia")
    elif temp > 39.5: alertas.append("Hipertermia")

    if profundo >= 2:
        msg_base = "PLANO PROFUNDO"
        cor, icone = "red", "🚨"
    elif superficial >= 2:
        msg_base = "PLANO SUPERFICIAL/DOR"
        cor, icone = "orange", "⚠️"
    else:
        msg_base = "Plano Estável"
        cor = "green" if len(alertas) == 0 else "orange"
        icone = "✅" if len(alertas) == 0 else "⚠️"
        if "Hipóxia Severa" in alertas: cor, icone = "red", "🚨"

    if len(alertas) > 0: return f"{msg_base}: {', '.join(alertas)}", cor, icone
    else: return msg_base, cor, icone

def gerar_pdf(df, dados):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_fill_color(33, 37, 41) 
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 15, " PRONTUARIO DE MONITORAMENTO ANESTESICO", ln=True, fill=True, align='C')
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 11)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 8, " 1. IDENTIFICACAO DO PACIENTE", border='B', ln=True, fill=True)
    
    risco_asa = dados['asa'].split(' (')[0] 
    
    pdf.set_font("Arial", '', 10)
    pdf.cell(100, 8, f"Paciente: {dados['nome']} (Prontuario: {dados['id_paciente']})", ln=0)
    pdf.cell(90, 8, f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=1)
    pdf.cell(100, 8, f"Especie/Porte: {dados['especie']}", ln=0)
    pdf.cell(90, 8, f"Raca: {dados['raca']}", ln=1)
    pdf.cell(100, 8, f"Peso: {dados['peso']} kg", ln=0)
    pdf.cell(90, 8, f"Risco Cirurgico: {risco_asa}", ln=1)
    pdf.cell(0, 8, f"Procedimento: {dados['procedimento']}", ln=1)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, " 2. HISTORICO DE PARAMETROS VITAIS", border='B', ln=True, fill=True)
    
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(15, 8, "Hora", 1, 0, 'C')
    pdf.cell(15, 8, "FC", 1, 0, 'C')
    pdf.cell(15, 8, "FR", 1, 0, 'C')
    pdf.cell(15, 8, "PAS", 1, 0, 'C')
    pdf.cell(15, 8, "SpO2", 1, 0, 'C')
    pdf.cell(15, 8, "Temp", 1, 0, 'C')
    pdf.cell(100, 8, "Ocorrencia / Alerta Clinico", 1, 1, 'C')

    for i, row in df.iterrows():
        pdf.set_font("Arial", '', 8)
        pdf.cell(15, 6, str(row['Hora']), 1, 0, 'C')
        pdf.cell(15, 6, str(row['FC']), 1, 0, 'C')
        pdf.cell(15, 6, str(row['FR']), 1, 0, 'C')
        pdf.cell(15, 6, str(row['PAS']), 1, 0, 'C')
        pdf.cell(15, 6, str(row['SpO2']), 1, 0, 'C')
        pdf.cell(15, 6, str(row['Temp']), 1, 0, 'C')
        
        pdf.set_font("Arial", '', 7)
        alerta_txt = str(row['Alertas'])
        if len(alerta_txt) > 75: alerta_txt = alerta_txt[:72] + "..."
        pdf.cell(100, 6, alerta_txt, 1, 1, 'L')
    
    # ==========================================
    # GERAÇÃO DO GRÁFICO ESTÁTICO PARA O PDF
    # ==========================================
    if not df.empty and len(df) > 1:
        if pdf.get_y() > 130:  # Quebra de página se não houver espaço
            pdf.add_page()
            
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 8, " 3. GRAFICO DE TENDENCIA (COMPLETO)", border='B', ln=True, fill=True)
        pdf.ln(5)

        # Desenha o gráfico usando o Matplotlib (funciona em qualquer servidor)
        plt.figure(figsize=(10, 4.5))
        plt.plot(df['Hora'], df['FC'], label='FC (bpm)', color='#e74c3c', marker='o', linewidth=2)
        plt.plot(df['Hora'], df['PAS'], label='PAS (mmHg)', color='#3498db', marker='s', linewidth=2)
        plt.plot(df['Hora'], df['FR'], label='FR (mpm)', color='#2ecc71', linestyle='--', marker='^')
        plt.plot(df['Hora'], df['SpO2'], label='SpO2 (%)', color='#9b59b6', linestyle=':', marker='d')
        
        # Desenha a zona verde alvo da Frequência Cardíaca
        plt.axhspan(LIMITES[dados['especie']]['FC']['min'], LIMITES[dados['especie']]['FC']['max'], 
                    color='green', alpha=0.1, label='Zona Alvo FC')
        
        plt.title('Evolucao dos Parametros Trans-operatorios', fontsize=12)
        plt.xlabel('Hora da Afericao')
        plt.ylabel('Valores Vitais')
        plt.legend(loc='upper right', fontsize=8, bbox_to_anchor=(1.15, 1))
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.tight_layout()

        # Salva o gráfico desenhado numa imagem temporária
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
            plt.savefig(tmpfile.name, format='png', dpi=150)
            y_atual = pdf.get_y()
            pdf.image(tmpfile.name, x=10, y=y_atual, w=190)
            pdf.set_y(y_atual + 100) # Avança o cursor para não atropelar a imagem
            
        os.remove(tmpfile.name)
        plt.close() # Limpa a memória
    else:
        pdf.ln(10)
        pdf.set_font("Arial", 'I', 9)
        pdf.cell(0, 5, "Grafico requer pelo menos duas afericoes para ser gerado.", ln=1)

    # Assinatura (Com margem de segurança)
    pdf.ln(25)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, "________________________________________________________", ln=1, align='C')
    pdf.cell(0, 5, "Assinatura e Carimbo do Anestesiologista Veterinario", ln=1, align='C')
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# BARRA LATERAL (PAINEL DE EMERGÊNCIA)
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2865/2865909.png", width=60)
    st.markdown("## Painel de Emergência")
    
    if st.session_state.dados_confirmados:
        peso = st.session_state.dados_paciente["peso"]
        esp = st.session_state.dados_paciente["especie"]
        
        st.info(f"🐶 **{st.session_state.dados_paciente['nome']}** | ⚖️ **{peso} kg**\n\n⚠️ {st.session_state.dados_paciente['asa']}")
        st.divider()
        
        for farmaco, info in FARMACOS_EMERGENCIA[esp].items():
            dose_total = info["dose"] * peso
            st.error(f"💉 **{farmaco}**\n\nPreparar: **{dose_total:.2f} {info['unidade']}**\n\n_{info['obs']}_")
    else:
        st.warning("Confirme os dados do paciente para liberar as doses calculadas.")

# ==========================================
# INTERFACE PRINCIPAL
# ==========================================
st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🩺 Prontuário Digital de Anestesia Vet</h1>", unsafe_allow_html=True)
st.markdown("---")

aba_paciente, aba_transop = st.tabs(["📋 1. Admissão do Paciente", "📈 2. Monitoramento Cirúrgico"])

# ------------------------------------------
# ABA 1: DADOS DO PACIENTE
# ------------------------------------------
with aba_paciente:
    st.markdown("### Ficha de Avaliação Pré-Anestésica")
    
    with st.form("form_cadastro_paciente"):
        col1, col2 = st.columns(2)
        with col1:
            id_paciente = st.text_input("Nº do Prontuário / ID:", value=st.session_state.dados_paciente["id_paciente"])
            nome = st.text_input("Nome do Paciente:", value=st.session_state.dados_paciente["nome"])
            especie = st.selectbox("Espécie/Porte:", ["Cão (Pequeno Porte)", "Cão (Grande Porte)", "Gato"])
            procedimento = st.text_input("Procedimento Cirúrgico:", value=st.session_state.dados_paciente["procedimento"])
            
        with col2:
            peso = st.number_input("Peso (kg):", min_value=0.0, step=0.1, value=float(st.session_state.dados_paciente["peso"]))
            raca = st.text_input("Raça:", value=st.session_state.dados_paciente["raca"])
            asa = st.selectbox("Classificação de Risco (ASA):", [
                "ASA I (Normal/Saudável)", "ASA II (Doença sistêmica leve)", 
                "ASA III (Doença sistêmica grave)", "ASA IV (Risco de vida constante)", 
                "ASA V (Moribundo - <24h de sobrevida)"
            ])

        st.markdown("<br>", unsafe_allow_html=True)
        submit_dados = st.form_submit_button("✅ Validar e Iniciar Prontuário Médico", type="primary", use_container_width=True)

    if submit_dados:
        if peso <= 0 or nome == "":
            st.error("Nome e Peso são obrigatórios.")
        else:
            st.session_state.dados_paciente = {
                "nome": nome, "id_paciente": id_paciente, "raca": raca, 
                "peso": peso, "especie": especie, "procedimento": procedimento, "asa": asa
            }
            st.session_state.dados_confirmados = True
            st.success("Prontuário gerado com sucesso! Acesse a aba 'Monitoramento Cirúrgico'.")

# ------------------------------------------
# ABA 2: MONITORAMENTO TRANS-OPERATÓRIO
# ------------------------------------------
with aba_transop:
    if not st.session_state.dados_confirmados:
        st.info("⚠️ Aguardando admissão do paciente na aba anterior.")
    else:
        col_resumo, col_timer = st.columns([2, 1])
        with col_resumo:
            st.markdown(f"### Paciente: {st.session_state.dados_paciente['nome']} ({st.session_state.dados_paciente['especie']})")
            st.markdown(f"**Procedimento:** {st.session_state.dados_paciente['procedimento']}")

        with col_timer:
            codigo_temporizador = """
            <div id="box-alarme" style="text-align: center; padding: 10px; border-radius: 8px; background-color: #f8f9fa; border: 1px solid #ddd;">
                <h4 id="timer" style="color: #333; margin: 0; font-size: 18px;">⏳ Aguardando...</h4>
                
                <div style="margin-top: 8px; display: flex; justify-content: center; gap: 5px; flex-wrap: wrap;">
                    <button id="btn-start" onclick="startTimer()" style="padding: 5px 10px; background-color: #ff4b4b; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer;">▶ Iniciar</button>
                    <button id="btn-pause" onclick="pauseTimer()" style="display: none; padding: 5px 10px; background-color: #666; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer;">⏹ Pausar</button>
                    <button id="btn-stop-alarm" onclick="stopAlarm(true)" style="display: none; padding: 5px 10px; background-color: #333; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer;">🔕 Silenciar</button>
                </div>
                
                <div style="margin-top: 10px;">
                    <select id="intervalo" onchange="resetTimerManually()" style="padding: 4px; border-radius: 4px; font-size: 13px;">
                        <option value="300">5 minutos</option>
                        <option value="600">10 minutos</option>
                        <option value="900">15 minutos</option>
                        <option value="10">10 segundos (Teste)</option>
                    </select>
                </div>
            </div>

            <script>
                let interval, alarmInterval, audioCtx = null;
                let alarmActive = false, isRunning = false;

                function getSelectedTime() { return parseInt(document.getElementById("intervalo").value); }
                function playBeep(freq = 880) {
                    if (!audioCtx) return;
                    const osc = audioCtx.createOscillator(), gain = audioCtx.createGain();
                    osc.type = 'sine'; osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
                    gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.4);
                    osc.connect(gain); gain.connect(audioCtx.destination); osc.start(); osc.stop(audioCtx.currentTime + 0.5);
                }

                function updateDisplay(time) {
                    if (time === undefined) return;
                    let min = Math.floor(time / 60), sec = time % 60;
                    document.getElementById("timer").innerText = "⏳ Aferição: " + (min < 10 ? "0" : "") + min + ":" + (sec < 10 ? "0" : "") + sec;
                }

                function startTimer() {
                    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                    if (audioCtx.state === 'suspended') audioCtx.resume();
                    
                    isRunning = true;
                    document.getElementById("btn-pause").style.display = "inline-block";
                    document.getElementById("btn-start").innerText = "▶ Reiniciar";
                    
                    playBeep(440); 
                    stopAlarm(false);
                    window.timeLeft = getSelectedTime();
                    updateDisplay(window.timeLeft);
                    
                    clearInterval(interval);
                    interval = setInterval(() => {
                        if (!alarmActive && isRunning) {
                            window.timeLeft--;
                            updateDisplay(window.timeLeft);
                            if(window.timeLeft <= 0) triggerAlarm();
                        }
                    }, 1000);
                }

                function pauseTimer() {
                    isRunning = false;
                    clearInterval(interval);
                    document.getElementById("btn-pause").style.display = "none";
                    document.getElementById("btn-start").innerText = "▶ Retomar";
                    document.getElementById("timer").innerText = "⏹ Pausado";
                }

                function resetTimerManually() {
                    window.timeLeft = getSelectedTime();
                    if (!isRunning) {
                        document.getElementById("timer").innerText = "⏳ Aguardando...";
                        document.getElementById("btn-start").innerText = "▶ Iniciar";
                    } else {
                        updateDisplay(window.timeLeft);
                    }
                }

                function triggerAlarm() {
                    alarmActive = true;
                    document.getElementById("box-alarme").style.backgroundColor = "#ffdada";
                    document.getElementById("btn-stop-alarm").style.display = "inline-block";
                    document.getElementById("btn-pause").style.display = "none";
                    alarmInterval = setInterval(() => { playBeep(880); setTimeout(() => playBeep(880), 500); }, 2000);
                }

                function stopAlarm(resetTime = true) {
                    alarmActive = false;
                    clearInterval(alarmInterval);
                    document.getElementById("box-alarme").style.backgroundColor = "#f8f9fa";
                    document.getElementById("btn-stop-alarm").style.display = "none";
                    if (isRunning) document.getElementById("btn-pause").style.display = "inline-block";
                    if (resetTime) { window.timeLeft = getSelectedTime(); updateDisplay(window.timeLeft); }
                }

                window.parent.addEventListener('message', function(e) {
                    if (e.data === 'reset_timer_via_python') {
                        if (isRunning || alarmActive) {
                            stopAlarm(true);
                            playBeep(660); 
                        }
                    }
                });
            </script>
            """
            components.html(codigo_temporizador, height=170)

        st.markdown("---")

        with st.form("registro_op", clear_on_submit=True):
            st.markdown("#### 📝 Inserir Parâmetros Vitais")
            col1, col2, col3, col4, col5 = st.columns(5)
            fc = col1.number_input("❤️ FC (bpm)", min_value=0, step=1)
            pas = col2.number_input("🩸 PAS (mmHg)", min_value=0, step=1)
            fr = col3.number_input("🫁 FR (mpm)", min_value=0, step=1)
            spo2 = col4.number_input("💨 SpO2 (%)", min_value=0, max_value=100, value=98, step=1)
            temp = col5.number_input("🌡️ Temp (°C)", min_value=0.0, value=38.0, step=0.1)
            
            st.markdown("<br>", unsafe_allow_html=True)
            btn_reg = st.form_submit_button("Salvar Leitura e Reiniciar Relógio", type="primary", use_container_width=True)

        if btn_reg:
            comando_js = f"<script>window.parent.postMessage('reset_timer_via_python', '*'); /* {time.time()} */</script>"
            components.html(comando_js, height=0)

            esp = st.session_state.dados_paciente["especie"]
            msg_txt, cor_plano, icone = avaliar_parametros_completos(fc, fr, pas, spo2, temp, LIMITES[esp])
            
            if cor_plano == "red": st.error(f"{icone} {msg_txt}")
            elif cor_plano == "orange": st.warning(f"{icone} {msg_txt}")
            else: st.success(f"{icone} {msg_txt}")

            nova_leitura = pd.DataFrame([{
                'Hora': datetime.now().strftime("%H:%M:%S"), 
                'FC': fc, 'FR': fr, 'PAS': pas, 'SpO2': spo2, 'Temp': temp,
                'Alertas': msg_txt
            }])
            st.session_state.historico_vet = pd.concat([st.session_state.historico_vet, nova_leitura], ignore_index=True)

        if not st.session_state.historico_vet.empty:
            df = st.session_state.historico_vet
            
            st.markdown("#### 📊 Gráfico de Tendência (Completo)")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df['Hora'], y=df['FC'], name="FC (bpm)", line=dict(color='#e74c3c', width=3), mode='lines+markers'))
            fig.add_trace(go.Scatter(x=df['Hora'], y=df['PAS'], name="PAS (mmHg)", line=dict(color='#3498db', width=3), mode='lines+markers'))
            fig.add_trace(go.Scatter(x=df['Hora'], y=df['FR'], name="FR (mpm)", line=dict(color='#2ecc71', width=2, dash='dash'), mode='lines+markers'))
            fig.add_trace(go.Scatter(x=df['Hora'], y=df['SpO2'], name="SpO2 (%)", line=dict(color='#9b59b6', width=2, dash='dot'), mode='lines+markers'))
            fig.add_trace(go.Scatter(x=df['Hora'], y=df['Temp'], name="Temp (°C)", line=dict(color='#f39c12', width=2, dash='dashdot'), mode='lines+markers'))
            
            esp = st.session_state.dados_paciente["especie"]
            fig.add_hrect(y0=LIMITES[esp]["FC"]["min"], y1=LIMITES[esp]["FC"]["max"], fillcolor="green", opacity=0.1, line_width=0, annotation_text="Zona Alvo FC")
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0), hovermode="x unified", template="plotly_white")
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            col_tabela, col_pdf = st.columns([3, 1])
            with col_tabela:
                st.markdown("#### 📑 Histórico Completo com Ocorrências")
                st.dataframe(df, use_container_width=True, hide_index=True)
            
            with col_pdf:
                st.markdown("#### 🖨️ Exportação")
                nome_arquivo = f"Prontuario_{st.session_state.dados_paciente['nome']}.pdf"
                
                # Gera o PDF com gráfico estático nativo
                pdf_data = gerar_pdf(df, st.session_state.dados_paciente)
                
                st.download_button(
                    label="📥 Gerar e Baixar PDF Final",
                    data=pdf_data,
                    file_name=nome_arquivo,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )
