/**
 * 音声認識システム - OpenAI Whisper API使用
 * 日本語デフォルト、10秒制限、言語切り替え対応
 */

class SpeechRecognitionSystem {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.recordingTimeout = null;
        this.language = 'ja'; // デフォルトは日本語
        this.maxRecordingTime = 20000; // 20秒制限
        
        // 利用可能な言語
        this.supportedLanguages = {
            'ja': '日本語',
            'en': 'English',
            'ko': '한국어',
            'zh': '中文',
            'auto': '自動検出'
        };
    }
    
    /**
     * 音声録音を開始
     */
    async startRecording(callback, errorCallback, uiCallback) {
        try {
            // マイクへのアクセス許可を取得
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            
            // 音量レベル監視用のAudioContextを作成
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioContext.createAnalyser();
            this.microphone = this.audioContext.createMediaStreamSource(stream);
            this.microphone.connect(this.analyser);
            this.analyser.fftSize = 256;
            this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
            
            // MediaRecorderを初期化
            this.mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus'
            });
            
            this.audioChunks = [];
            this.isRecording = true;
            this.recordingStartTime = Date.now();
            
            // 音声データを収集
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            // 録音停止時の処理
            this.mediaRecorder.onstop = () => {
                this.processRecording(callback, errorCallback);
                stream.getTracks().forEach(track => track.stop());
                if (this.audioContext) {
                    this.audioContext.close();
                }
            };
            
            // 録音開始
            this.mediaRecorder.start();
            
            // リアルタイム更新
            this.updateRecordingUI(uiCallback);
            
            // 10秒で自動停止
            this.recordingTimeout = setTimeout(() => {
                this.stopRecording();
            }, this.maxRecordingTime);
            
            console.log(`録音開始 (${this.supportedLanguages[this.language]}, 最大${this.maxRecordingTime/1000}秒)`);
            
        } catch (error) {
            console.error('録音開始エラー:', error);
            if (errorCallback) {
                errorCallback('マイクへのアクセスが許可されていません');
            }
        }
    }
    
    /**
     * 録音中のUI更新
     */
    updateRecordingUI(uiCallback) {
        if (!this.isRecording) return;
        
        const elapsed = Date.now() - this.recordingStartTime;
        const remaining = Math.max(0, Math.ceil((this.maxRecordingTime - elapsed) / 1000));
        
        // 音量レベルを取得
        this.analyser.getByteFrequencyData(this.dataArray);
        const average = this.dataArray.reduce((a, b) => a + b) / this.dataArray.length;
        const volumeLevel = Math.min(8, Math.floor(average / 32)); // 0-8のレベル
        
        if (uiCallback) {
            uiCallback(remaining, volumeLevel);
        }
        
        // 次のフレームで更新
        requestAnimationFrame(() => this.updateRecordingUI(uiCallback));
    }
    
    /**
     * 音声録音を停止
     */
    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            
            if (this.recordingTimeout) {
                clearTimeout(this.recordingTimeout);
                this.recordingTimeout = null;
            }
            
            console.log('録音停止');
        }
    }
    
    /**
     * 録音した音声を処理してテキスト変換
     */
    async processRecording(callback, errorCallback) {
        try {
            if (this.audioChunks.length === 0) {
                throw new Error('音声データがありません');
            }
            
            // 音声データをBlobに変換
            const audioBlob = new Blob(this.audioChunks, { 
                type: 'audio/webm;codecs=opus' 
            });
            
            // FormDataを作成
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');
            formData.append('language', this.language);
            
            console.log('音声認識APIに送信中...');
            
            // APIに送信
            const response = await fetch('/api/speech-to-text', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                console.log('音声認識成功:', result.text);
                if (callback) {
                    callback(result.text);
                }
            } else {
                throw new Error(result.error || '音声認識に失敗しました');
            }
            
        } catch (error) {
            console.error('音声処理エラー:', error);
            if (errorCallback) {
                errorCallback(error.message);
            }
        }
    }
    
    /**
     * 言語を設定
     */
    setLanguage(language) {
        if (this.supportedLanguages[language]) {
            this.language = language;
            console.log(`音声認識言語を${this.supportedLanguages[language]}に設定`);
        }
    }
    
    /**
     * 録音時間制限を設定（ミリ秒）
     */
    setMaxRecordingTime(milliseconds) {
        this.maxRecordingTime = milliseconds;
    }
    
    /**
     * 録音中かどうかを確認
     */
    isCurrentlyRecording() {
        return this.isRecording;
    }
    
    /**
     * サポートされている言語一覧を取得
     */
    getSupportedLanguages() {
        return this.supportedLanguages;
    }
}

/**
 * 音声入力ボタンUIを作成
 */
function createVoiceInputButton(targetInputId, options = {}) {
    const speechSystem = new SpeechRecognitionSystem();
    
    // オプション設定
    const config = {
        language: options.language || 'ja',
        maxTime: options.maxTime || 20000,
        buttonText: options.buttonText || '🎤',
        showLanguageSelect: options.showLanguageSelect !== false,
        fixedLanguage: options.fixedLanguage || false, // 言語固定オプション
        ...options
    };
    
    speechSystem.setLanguage(config.language);
    speechSystem.setMaxRecordingTime(config.maxTime);
    
    // UIコンテナを作成
    const container = document.createElement('div');
    container.className = 'voice-input-container';
    container.style.cssText = `
        display: inline-flex;
        align-items: center;
        gap: 8px;
        margin: 4px;
    `;
    
    // 音声入力ボタン
    const voiceButton = document.createElement('button');
    voiceButton.type = 'button';
    voiceButton.className = 'voice-input-btn';
    voiceButton.innerHTML = config.buttonText;
    voiceButton.title = '音声入力 (最大20秒)';
    voiceButton.style.cssText = `
        padding: 6px 10px;
        background: #E0E0E0;
        border: 2px solid #000;
        border-bottom: 3px solid #808080;
        border-right: 3px solid #808080;
        color: #000;
        font-size: 14px;
        cursor: pointer;
        user-select: none;
        min-width: 100px;
        text-align: center;
    `;
    
    // 言語選択セレクト（固定言語でない場合のみ）
    let languageSelect = null;
    if (config.showLanguageSelect && !config.fixedLanguage) {
        languageSelect = document.createElement('select');
        languageSelect.className = 'voice-language-select';
        languageSelect.style.cssText = `
            padding: 2px 4px;
            border: 1px solid #808080;
            font-size: 10px;
            background: #F0F0F0;
        `;
        
        // 言語オプションを追加
        Object.entries(speechSystem.getSupportedLanguages()).forEach(([code, name]) => {
            const option = document.createElement('option');
            option.value = code;
            option.textContent = name;
            if (code === config.language) {
                option.selected = true;
            }
            languageSelect.appendChild(option);
        });
        
        // 言語変更時の処理
        languageSelect.addEventListener('change', () => {
            speechSystem.setLanguage(languageSelect.value);
        });
        
        container.appendChild(languageSelect);
    }
    
    // レトロな音量メーターを作成する関数
    function createVolumeLevel(level) {
        let meter = '🎤 ';
        for (let i = 0; i < 8; i++) {
            if (i < level) {
                meter += '█';
            } else {
                meter += '░';
            }
        }
        return meter;
    }
    
    // ボタンクリック処理
    voiceButton.addEventListener('click', () => {
        const targetInput = document.getElementById(targetInputId);
        if (!targetInput) {
            alert('入力フィールドが見つかりません');
            return;
        }
        
        if (speechSystem.isCurrentlyRecording()) {
            // 録音中なら停止
            speechSystem.stopRecording();
            voiceButton.innerHTML = config.buttonText;
            voiceButton.style.background = '#E0E0E0';
            voiceButton.style.fontSize = '14px';
            voiceButton.title = '音声入力 (最大20秒)';
        } else {
            // 録音開始
            speechSystem.startRecording(
                // 成功コールバック
                (text) => {
                    targetInput.value = text;
                    targetInput.focus();
                    voiceButton.innerHTML = config.buttonText;
                    voiceButton.style.background = '#E0E0E0';
                    voiceButton.style.fontSize = '14px';
                    voiceButton.title = '音声入力 (最大20秒)';
                    
                    // 入力イベントをトリガー
                    targetInput.dispatchEvent(new Event('input', { bubbles: true }));
                },
                // エラーコールバック
                (error) => {
                    alert(`音声認識エラー: ${error}`);
                    voiceButton.innerHTML = config.buttonText;
                    voiceButton.style.background = '#E0E0E0';
                    voiceButton.style.fontSize = '14px';
                    voiceButton.title = '音声入力 (最大20秒)';
                },
                // UIコールバック（録音中の表示）
                (remaining, volumeLevel) => {
                    const volumeMeter = createVolumeLevel(volumeLevel);
                    voiceButton.innerHTML = `${volumeMeter}<br>残り${remaining}秒`;
                    voiceButton.style.background = '#FFD0D0';
                    voiceButton.style.fontSize = '9px';
                    voiceButton.style.lineHeight = '1.2';
                    voiceButton.title = `録音中... 残り${remaining}秒 (クリックで停止)`;
                }
            );
        }
    });
    
    container.appendChild(voiceButton);
    
    return {
        container: container,
        speechSystem: speechSystem,
        button: voiceButton,
        languageSelect: languageSelect
    };
}

// グローバルに公開
window.SpeechRecognitionSystem = SpeechRecognitionSystem;
window.createVoiceInputButton = createVoiceInputButton;