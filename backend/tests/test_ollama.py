from app.llm import llm


def test_local_model_responds():
    response = llm.invoke(
        "In one sentence, explain what a duplicate API usage event means."
    )

    assert response.content
    print(response.content)


if __name__ == "__main__":
    test_local_model_responds()