# Private GitHub repo — Is intraoperative hypotension associated with postoperative acute kidney injury?

This scoping pack is laid out as a clone-ready repository (code, analysis plan, data dictionary, figure templates). It does **not** contain patient data — `extract_vitaldb.py` pulls the open VitalDB subset on your machine.

## Push it
Create a private repo and push (GitHub CLI):

    git init && git add . && git commit -m "Afferent scoping pack"
    gh repo create afferent-study --private --source=. --push

…or create an empty private repo on github.com, then add it as `origin` and push.

## Run it
    pip install -r requirements.txt
    python extract_vitaldb.py
    python make_plots.py
