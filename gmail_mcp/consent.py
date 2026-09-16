from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from .oauth_provider import check_passphrase, issue_code_and_redirect, peek_pending, pop_pending

FORM = """<!doctype html>
<html><body style="font-family: sans-serif; max-width: 420px; margin: 80px auto;">
<h2>Authorize Gmail access</h2>
<p>A connector is requesting read and draft access to your Gmail through this server.</p>
{error}
<form method="post" action="/consent">
  <input type="hidden" name="txn" value="{txn}">
  <label for="passphrase">Passphrase</label><br>
  <input id="passphrase" type="password" name="passphrase" autofocus
         style="width:100%;padding:8px;margin:8px 0;box-sizing:border-box;">
  <button type="submit" style="padding:8px 16px;">Approve</button>
</form>
</body></html>
"""

EXPIRED = HTMLResponse(
    "<p>This authorization request has expired. Go back and try connecting again.</p>", status_code=400
)


async def consent_get(request: Request) -> HTMLResponse:
    txn = request.query_params.get("txn", "")
    if peek_pending(txn) is None:
        return EXPIRED
    return HTMLResponse(FORM.format(txn=txn, error=""))


async def consent_post(request: Request):
    form = await request.form()
    txn = str(form.get("txn", ""))
    passphrase = str(form.get("passphrase", ""))

    pending = peek_pending(txn)
    if pending is None:
        return EXPIRED

    if not check_passphrase(passphrase):
        return HTMLResponse(
            FORM.format(txn=txn, error="<p style='color:red'>Incorrect passphrase.</p>"),
            status_code=401,
        )

    pending = pop_pending(txn)
    redirect_url = issue_code_and_redirect(pending)
    return RedirectResponse(redirect_url, status_code=302)
