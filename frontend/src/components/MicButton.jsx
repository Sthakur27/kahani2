import { useEffect, useRef } from "react";
import { useSpeechToText } from "@mazka/react-speech-to-text";

// Small icon-style mic button that drives the @mazka/react-speech-to-text
// `useSpeechToText` hook. When the user stops dictating, the final transcript
// is handed back via `onTranscript` so the parent can append it to a field's
// state. If the browser doesn't support the Web Speech API the button hides
// itself rather than breaking the form.
export default function MicButton({ onTranscript, label = "field" }) {
  const {
    isListening,
    isSupported,
    finalTranscript,
    startListening,
    stopListening,
    resetTranscript,
    error,
  } = useSpeechToText({ continuous: true, interimResults: true, language: "en-US" });

  // Track how much of the final transcript we've already flushed into the
  // field, so each dictation session only appends what's new.
  const flushedRef = useRef("");

  // Append newly-finalized speech to the field as it arrives.
  useEffect(() => {
    if (!finalTranscript) return;
    const fresh = finalTranscript.slice(flushedRef.current.length);
    if (fresh.trim()) {
      onTranscript(fresh);
      flushedRef.current = finalTranscript;
    }
  }, [finalTranscript, onTranscript]);

  if (!isSupported) return null;

  function handleClick() {
    if (isListening) {
      stopListening();
    } else {
      flushedRef.current = "";
      resetTranscript();
      startListening();
    }
  }

  return (
    <button
      type="button"
      className={`mic-btn${isListening ? " mic-btn--listening" : ""}`}
      onClick={handleClick}
      aria-pressed={isListening}
      aria-label={
        isListening ? `Stop dictating ${label}` : `Dictate ${label} by voice`
      }
      title={
        error
          ? error.message
          : isListening
            ? "Listening… click to stop"
            : "Dictate by voice"
      }
    >
      <span aria-hidden="true">{isListening ? "■" : "🎤"}</span>
    </button>
  );
}
