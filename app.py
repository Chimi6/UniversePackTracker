import uuid
import requests
from flask import Flask, render_template, session, request, redirect, url_for
from flask_session import Session  # https://pythonhosted.org/Flask-Session
import msal
import app_config
from forms import addPackage, packageDetail
import requests
import json


app = Flask(__name__)
app.config['SECRET_KEY'] = 'calebtest'
app.config.from_object(app_config)
Session(app)

# This section is needed for url_for("foo", _external=True) to automatically
# generate http scheme when this sample is running on localhost,
# and to generate https scheme when it is deployed behind reversed proxy.
# See also https://flask.palletsprojects.com/en/1.0.x/deploying/wsgi-standalone/#proxy-setups
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

@app.route("/")
def index():
    if not session.get("user"):
        return redirect(url_for("login"))
    return render_template('index.html', user=session["user"], version=msal.__version__)

@app.route("/home",methods=['GET', 'POST'])
def home():
    if not session.get("user"):
        return redirect(url_for("login"))
    form = addPackage()
    if form.is_submitted():
        result = request.form
        postToLogic(result)
        return render_template('packageAdded.html',user=session["user"], result=result)
    return render_template('home.html',form = form,user=session["user"])
@app.route("/packages")
def packages():
    form = packageDetail()
    if not session.get("user"):
        return redirect(url_for("login"))
    packageList =getPackages()
    return render_template('packages.html', cards=packageList, user=session["user"], form = form)
@app.route('/package/<packageId>')
def package(packageId):
    if not session.get("user"):
        return redirect(url_for("login"))
    # Technically this should be a PUT request as part of REST
    
    #id = request.args.id
    return render_template('package.html', user=session["user"])
@app.route('/packageHandler', methods=['POST'])
def changeId():
    if not session.get("user"):
        return redirect(url_for("login"))
    # Technically this should be a PUT request as part of REST
    if request.method == 'POST':
        newId = request.form.getlist("id")[0][:-1]
    #id = request.args.id
    return redirect(url_for('package', packageId=newId))
@app.route("/login")
def login():
    # Technically we could use empty list [] as scopes to do just sign in,
    # here we choose to also collect end user consent upfront
    session["flow"] = _build_auth_code_flow(scopes=app_config.SCOPE)
    return render_template("login.html", auth_url=session["flow"]["auth_uri"], version=msal.__version__)

@app.route(app_config.REDIRECT_PATH)  # Its absolute URL must match your app's redirect_uri set in AAD
def authorized():
    try:
        cache = _load_cache()
        result = _build_msal_app(cache=cache).acquire_token_by_auth_code_flow(
            session.get("flow", {}), request.args)
        if "error" in result:
            return render_template("auth_error.html", result=result)
        session["user"] = result.get("id_token_claims")
        _save_cache(cache)
    except ValueError:  # Usually caused by CSRF
        pass  # Simply ignore them
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.clear()  # Wipe out user and its token cache from session
    return redirect(  # Also logout from your tenant's web session
        app_config.AUTHORITY + "/oauth2/v2.0/logout" +
        "?post_logout_redirect_uri=" + url_for("index", _external=True))

@app.route("/graphcall")
def graphcall():
    token = _get_token_from_cache(app_config.SCOPE)
    if not token:
        return redirect(url_for("login"))
    graph_data=getGraph()
    return render_template('display.html', result=graph_data)

def getGraph():
    token = _get_token_from_cache(app_config.SCOPE)
    if not token:
        return redirect(url_for("login"))
    graph_data = requests.get(  # Use token to call downstream service
        app_config.ENDPOINT,
        headers={'Authorization': 'Bearer ' + token['access_token']},
        ).json()
    return graph_data

def postToLogic(form):
    graph_data = getGraph()
    userId= graph_data["value"][0]["id"]
    url = "https://prod-20.centralus.logic.azure.com:443/workflows/f8d4e0a14e9243399f47eb3e53b7cadc/triggers/manual/paths/invoke?api-version=2016-10-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=pRkOaOCdSR4yzZwfjHp4lPzSSdF_uzbI2o9CoA0A7Ko"

    payload = json.dumps({
    "userId": "{}".format(userId),
    "userName": "{}".format(session["user"]["name"]),
    "shippmentNumber": "{}".format(form["packageNumber"]),
    "carrier": "{}".format(form["carrier"]),
    "packageName": "{}".format(form["packageName"])
    })
    headers = {
    'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)

    print(response.text)

def getPackages():
    graph_data = getGraph()
    userId= graph_data["value"][0]["id"]
    
    url = "https://cc-capstone-db-handler.azurewebsites.net/api/databaseapi?code=aLPqYweCCdCOhBOojQqOz/qbjia3fibVC8d/pggxiagmGZj4y8eW5A==&userId={}".format(userId)

    payload={}
    headers = {}

    response = requests.request("GET", url, headers=headers, data=payload)

    return json.loads(response.text).get("message")

def _load_cache():
    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    return cache

def _save_cache(cache):
    if cache.has_state_changed:
        session["token_cache"] = cache.serialize()

def _build_msal_app(cache=None, authority=None):
    return msal.ConfidentialClientApplication(
        app_config.CLIENT_ID, authority=authority or app_config.AUTHORITY,
        client_credential=app_config.CLIENT_SECRET, token_cache=cache)

def _build_auth_code_flow(authority=None, scopes=None):
    return _build_msal_app(authority=authority).initiate_auth_code_flow(
        scopes or [],
        redirect_uri=url_for("authorized", _external=True))

def _get_token_from_cache(scope=None):
    cache = _load_cache()  # This web app maintains one cache per session
    cca = _build_msal_app(cache=cache)
    accounts = cca.get_accounts()
    if accounts:  # So all account(s) belong to the current signed-in user
        result = cca.acquire_token_silent(scope, account=accounts[0])
        _save_cache(cache)
        return result

app.jinja_env.globals.update(_build_auth_code_flow=_build_auth_code_flow)  # Used in template

if __name__ == "__main__":
    app.run(debug=True)

