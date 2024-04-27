import base64
from bson import ObjectId

from shared_components.models import Job, Sentence
from shared_components.utils import run_async

from worker.tts_adapter import LanguageNotSupportedException, send_tts_request


def update_progress(processed_sentences: int, all_sentences: int, job: Job):
    job.progress_percent = f"{(processed_sentences / all_sentences) * 100.0:.2f}"
    run_async(job.save())


def generate(job: Job):
    sentences = job.sanitized_text
    sentences_count = len(sentences)
    processed_sentences_count = 0
    print(f"Generating text for {sentences_count} sentences")
    for sentence_id in sentences:
        sentence = run_async(Sentence.find_one(Sentence.id == ObjectId(sentence_id)))
        print(
            f"Starting generating sentence {sentence}, language {sentence.language}, fallback language {job.language}"
        )
        try:
            audio_data = send_tts_request(
                sentence.text,
                language=sentence.language,
                fallback_language=job.language,
            )
            audio_bytes = audio_data.export(format="wav").read()
            audio_data_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            sentence.audio_data = audio_data_base64
            print(
                f"Saving generated audio to sentence {sentence.text}, content length {len(audio_data_base64)}"
            )
            run_async(sentence.save())
        except LanguageNotSupportedException as ex:
            # neither sentence language or whole text language are supported, skipping
            print(f"Error {ex}")
            continue
        processed_sentences_count += 1
        update_progress(
            processed_sentences=processed_sentences_count,
            all_sentences=sentences_count,
            job=job,
        )
    return sentences
