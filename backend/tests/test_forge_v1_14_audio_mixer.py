from app.ai.validators.schema_validator import validate_forge_document


def _doc(version="1.14"):
    return {
        "version": version,
        "initial_screen_id": "home",
        "screens": [{
            "id": "home", "title": "Audio", "state": {},
            "body": {"type": "audio_mixer", "id": "mixer",
                     "title": "Mix", "tracks": ["pulse", "chime", "bass"]},
        }],
    }


def test_v114_accepts_closed_local_audio_mixer_vocabulary():
    assert validate_forge_document(_doc()).valid


def test_v113_rejects_audio_mixer():
    result = validate_forge_document(_doc("1.13"))
    assert not result.valid
    assert any(e.rule == "widget_not_allowed_in_version" for e in result.errors)


def test_audio_mixer_rejects_unknown_track():
    doc = _doc()
    doc["screens"][0]["body"]["tracks"] = ["https://example.com/audio.wav"]
    result = validate_forge_document(doc)
    assert not result.valid
