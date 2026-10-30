"""A deterministic example of the adapter interface, returning the first label."""


def create():
    def answer(request):
        return {"answer": request["labels"][0]}

    return answer
