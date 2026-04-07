import requests
import json

class ForensicSketchBot:
    def __init__(self):
        # OpenRouter Key
        self.api_key = "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"

        # MAIN FLOW: Removed 'ears'. The sequence now correctly ends after 'hair'.
        self.steps = ['eyes', 'nose', 'mouth', 'hair']
        self.current_step_index = 0
        
        # State Flags
        self.awaiting_confirmation = False
        self.awaiting_regeneration_decision = False
        self.attributes = {}

        # VOCABULARY: Added 'beard' as an experimental module for future implementation.
        self.VOCABULARY = {
            'eyes': ['almond', 'hooded', 'monolid', 'round', 'narrow', 'bags'],
            'nose': ['narrow', 'big', 'wide', 'pointy', 'small', 'long', 'short'],
            'mouth': ['thin', 'full', 'thick', 'small', 'large', 'wide'],
            'hair': ['short', 'medium', 'long', 'thin', 'thick', 'straight', 'wavy', 'curly', 'bald'],
            
            # [ EXPERIMENTAL / FUTURE FEATURE ]
            'beard': ['goatee', 'stubble', 'full', 'mustache', 'clean'] 
        }

        self.FEATURE_HINTS = {
            'eyes': 'shape, size, and eyelid characteristics',
            'nose': 'width, overall size, and length',
            'mouth': 'thickness and width of the lips',
            'hair': 'length, thickness, style, and texture',
            
            # [ EXPERIMENTAL / FUTURE FEATURE ]
            'beard': 'facial hair style and length (EXPERIMENTAL)'
        }

    # ---------------------------------------------------
    # MAIN CONVERSATION FLOW
    # ---------------------------------------------------
    def handle_user_input(self, user_text):
        user_text = user_text.strip()

        # Finished case
        if self.current_step_index >= len(self.steps):
            return "SYSTEM: ALL MANDATORY FEATURES LOGGED. EXECUTING FULL SKETCH SYNTHESIS.", self.get_data()

        current_feature = self.steps[self.current_step_index]

        # -------------------------
        # PHASE 1: REGENERATION DECISION STAGE
        # -------------------------
        if self.awaiting_regeneration_decision:
            regen_intent = self.detect_regeneration_intent(user_text)
            
            if regen_intent == "REGENERATE":
                self.awaiting_regeneration_decision = False
                self.awaiting_confirmation = True
                return f"SYSTEM: RE-SYNTHESIZING {current_feature.upper()} WITH CURRENT PARAMETERS. CONFIRM NEW RENDER (YES/NO).", self.get_data()
            else:
                self.awaiting_regeneration_decision = False
                self.attributes[current_feature] = []
                hint = self.FEATURE_HINTS[current_feature]
                return f"SYSTEM: AWAITING NEW PARAMETERS FOR {current_feature.upper()}. (HINT: DESCRIBE {hint.upper()}).", self.get_data()

        # -------------------------
        # PHASE 2: CONFIRMATION STAGE
        # -------------------------
        if self.awaiting_confirmation:
            intent = self.detect_intent(user_text)

            if intent == "ACCEPT":
                self.awaiting_confirmation = False
                self.current_step_index += 1

                if self.current_step_index < len(self.steps):
                    next_feature = self.steps[self.current_step_index]
                    next_hint = self.FEATURE_HINTS[next_feature]
                    return f"SYSTEM: {current_feature.upper()} PARAMETERS LOCKED. PROCEED TO {next_feature.upper()}. (HINT: DESCRIBE {next_hint.upper()}).", self.get_data()
                else:
                    return "SYSTEM: ALL MANDATORY FEATURES LOGGED. EXECUTING FULL SKETCH SYNTHESIS.", self.get_data()

            elif intent == "REJECT":
                self.awaiting_confirmation = False
                self.awaiting_regeneration_decision = True
                return f"SYSTEM: DIRECTIVE REJECTED. DO YOU WISH TO [REGENERATE] WITH CURRENT PARAMETERS OR PROVIDE [NEW] PARAMETERS?", self.get_data()
            
            else:
                # User ignored YES/NO and just typed features again -> Treat as an update
                extracted_new = self.extract_attributes(user_text, current_feature)
                if extracted_new:
                    self.attributes[current_feature] = extracted_new
                    return f"SYSTEM: {current_feature.upper()} PARAMETERS UPDATED TO: [{', '.join(extracted_new).upper()}]. CONFIRM DIRECTIVE (YES/NO).", self.get_data()
                
                return f"SYSTEM: UNRECOGNIZED RESPONSE. PLEASE CONFIRM THE {current_feature.upper()} RENDER (YES/NO).", self.get_data()

        # -------------------------
        # PHASE 3: EXTRACTION STAGE
        # -------------------------
        extracted = self.extract_attributes(user_text, current_feature)

        if not extracted:
            hint = self.FEATURE_HINTS[current_feature]
            return f"SYSTEM: INSUFFICIENT DATA DETECTED. PLEASE DESCRIBE THE {current_feature.upper()} MORE CLEARLY. (HINT: {hint.upper()}).", self.get_data()

        self.attributes[current_feature] = extracted
        self.awaiting_confirmation = True

        return f"SYSTEM: {current_feature.upper()} DETECTED AS: [{', '.join(extracted).upper()}]. CONFIRM DIRECTIVE (YES/NO).", self.get_data()

    # ---------------------------------------------------
    # ATTRIBUTE EXTRACTION
    # ---------------------------------------------------
    def extract_attributes(self, text, feature):
        options = self.VOCABULARY[feature]
        text_lower = text.lower()

        # 1. Direct keyword match
        direct_matches = [opt for opt in options if opt in text_lower]
        if direct_matches:
            return direct_matches

        # 2. LLM fallback
        prompt = f"""
        You are a strict facial attribute classifier.
        User description: "{text}"
        Map the description ONLY to one or more of these exact attributes: {options}
        Rules: Return strictly valid JSON list. No explanation. No extra text. No markdown. If no match return [].
        """
        response = self.call_llm(prompt)
        try:
            parsed = json.loads(response)
            if isinstance(parsed, list):
                return [item for item in parsed if item in options]
        except:
            pass
        return []

    # ---------------------------------------------------
    # CONFIRMATION DETECTION
    # ---------------------------------------------------
    def detect_intent(self, text):
        positives = ["yes", "y", "correct", "right", "perfect", "okay", "fine", "looks good", "good", "confirm"]
        negatives = ["no", "n", "wrong", "change", "modify", "not correct", "bad", "reject"]
        text_lower = text.lower().strip()

        # Exact match to prevent "normal" from triggering "no"
        if any(text_lower == p or text_lower.startswith(p + " ") for p in positives): return "ACCEPT"
        if any(text_lower == n or text_lower.startswith(n + " ") for n in negatives): return "REJECT"

        prompt = f"""Classify this response: "{text}". If user agrees return ACCEPT. If user disagrees return REJECT."""
        response = self.call_llm(prompt)
        if "ACCEPT" in response.upper(): return "ACCEPT"
        if "REJECT" in response.upper(): return "REJECT"
        return "UNKNOWN"

    # ---------------------------------------------------
    # REGENERATION INTENT DETECTION
    # ---------------------------------------------------
    def detect_regeneration_intent(self, text):
        text_lower = text.lower()
        if any(w in text_lower for w in ["same", "regenerate", "yes", "keep", "again", "retry"]): return "REGENERATE"
        if any(w in text_lower for w in ["new", "change", "different", "re-describe"]): return "NEW"

        prompt = f"""Classify this user response: "{text}". 
        If user wants to regenerate using same attributes, return REGENERATE. 
        If user wants to provide new attributes, return NEW. Return ONLY one word."""
        response = self.call_llm(prompt)
        if "REGENERATE" in response.upper(): return "REGENERATE"
        return "NEW"

    # ---------------------------------------------------
    # SAFE LLM CALL (WITH TIMEOUT)
    # ---------------------------------------------------
    def call_llm(self, prompt):
        try:
            res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "google/gemini-2.0-flash-001",
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=10
            )
            data = res.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip().replace("```json", "").replace("```", "")
        except Exception as e:
            print("LLM FAILURE:", e)
            return ""

    def get_data(self):
        separated_vectors = {}
        combined_vector = []
        
        # We only generate vectors for the active steps (eyes, nose, mouth, hair)
        for feature in self.steps:
            feature_vector = []
            for keyword in self.VOCABULARY[feature]:
                val = 1 if keyword in self.attributes.get(feature, []) else 0
                feature_vector.append(val)
            separated_vectors[f"{feature}_vector"] = feature_vector
            combined_vector.extend(feature_vector)

        # UI FLAG: Tells the frontend what buttons to show
        if self.awaiting_regeneration_decision:
            ui_state = "REGEN_OR_NEW"
        elif self.awaiting_confirmation:
            ui_state = "CONFIRM_YES_NO"
        else:
            ui_state = "TEXT_INPUT"

        return {
            "structured": self.attributes,
            "separate_vectors": separated_vectors,
            "combined_vector": combined_vector,
            "ui_state": ui_state
        }
