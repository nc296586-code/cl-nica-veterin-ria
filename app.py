import os, sqlite3, hashlib, hmac
from pathlib import Path
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from cryptography.fernet import Fernet, InvalidToken

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "clinica_web.db"
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "troque-esta-chave-em-producao-por-uma-chave-secreta-longa")
FERNET_KEY = os.environ.get("FERNET_KEY")
if not FERNET_KEY:
    key_file = APP_DIR / "chave_web.key"
    if key_file.exists():
        FERNET_KEY = key_file.read_text().strip()
    else:
        FERNET_KEY = Fernet.generate_key().decode()
        key_file.write_text(FERNET_KEY)
fernet = Fernet(FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY)

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def hash_password(password, salt=None):
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + "$" + digest.hex()

def verify_password(password, saved):
    try:
        salt_hex, digest = saved.split("$", 1)
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000).hex()
        return hmac.compare_digest(calc, digest)
    except Exception:
        return False

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios(id INTEGER PRIMARY KEY, nome TEXT NOT NULL, usuario TEXT UNIQUE NOT NULL, senha_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tutores(id INTEGER PRIMARY KEY, nome TEXT NOT NULL, cpf_cifrado TEXT NOT NULL, telefone TEXT, email TEXT);
        CREATE TABLE IF NOT EXISTS pets(id INTEGER PRIMARY KEY, nome TEXT NOT NULL, especie TEXT NOT NULL, raca TEXT, idade INTEGER, tutor_id INTEGER NOT NULL REFERENCES tutores(id));
        CREATE TABLE IF NOT EXISTS agendamentos(id INTEGER PRIMARY KEY, data_hora TEXT NOT NULL, motivo TEXT NOT NULL, status TEXT NOT NULL, tutor_id INTEGER NOT NULL REFERENCES tutores(id), pet_id INTEGER NOT NULL REFERENCES pets(id));
        """)
        if con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
            con.executemany("INSERT INTO usuarios(nome,usuario,senha_hash) VALUES(?,?,?)", [
                ("Administrador","admin",hash_password("123456")),
                ("Maria Oliveira","maria",hash_password("maria123")),
                ("João Souza","joao",hash_password("joao123"))])
        if con.execute("SELECT COUNT(*) FROM tutores").fetchone()[0] == 0:
            seed = [("Maria Silva","11111111111","(62) 90000-0001","maria.teste@email.com"),
                    ("João Souza","22222222222","(62) 90000-0002","joao.teste@email.com"),
                    ("Ana Costa","33333333333","(62) 90000-0003","ana.teste@email.com")]
            for n,c,t,e in seed:
                con.execute("INSERT INTO tutores(nome,cpf_cifrado,telefone,email) VALUES(?,?,?,?)",(n,fernet.encrypt(c.encode()).decode(),t,e))
        if con.execute("SELECT COUNT(*) FROM pets").fetchone()[0] == 0:
            ids=[r["id"] for r in con.execute("SELECT id FROM tutores ORDER BY id LIMIT 3")]
            if len(ids)==3:
                con.executemany("INSERT INTO pets(nome,especie,raca,idade,tutor_id) VALUES(?,?,?,?,?)",
                    [("Rex","Cachorro","Labrador",4,ids[0]),("Mimi","Gato","SRD",2,ids[1]),("Bob","Cachorro","Poodle",5,ids[2])])
        if con.execute("SELECT COUNT(*) FROM agendamentos").fetchone()[0] == 0:
            rows=con.execute("SELECT id,tutor_id FROM pets ORDER BY id LIMIT 3").fetchall()
            if len(rows)==3:
                con.executemany("INSERT INTO agendamentos(data_hora,motivo,status,tutor_id,pet_id) VALUES(?,?,?,?,?)",[
                    ("2026-11-20 09:00","Consulta de rotina","Agendado",rows[0]["tutor_id"],rows[0]["id"]),
                    ("2026-11-21 10:30","Vacinação","Confirmado",rows[1]["tutor_id"],rows[1]["id"]),
                    ("2026-11-22 14:00","Avaliação","Agendado",rows[2]["tutor_id"],rows[2]["id"])])

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/", methods=["GET","POST"])
def login():
    if request.method=="POST":
        user=request.form.get("usuario","").strip()
        password=request.form.get("senha","")
        with db() as con:
            row=con.execute("SELECT id,nome,senha_hash FROM usuarios WHERE usuario=?",(user,)).fetchone()
        if row and verify_password(password,row["senha_hash"]):
            session["user_id"]=row["id"]; session["nome"]=row["nome"]
            return redirect(url_for("dashboard"))
        flash("Usuário ou senha incorretos.","danger")
    return render_template("login.html")

@app.route("/sair")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/inicio")
@login_required
def dashboard():
    with db() as con:
        counts={t:con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("tutores","pets","agendamentos")}
    return render_template("dashboard.html", counts=counts)

@app.route("/tutores", methods=["GET","POST"])
@login_required
def tutores():
    with db() as con:
        if request.method=="POST":
            rid=request.form.get("id")
            nome=request.form.get("nome","").strip(); cpf=request.form.get("cpf","").strip()
            telefone=request.form.get("telefone","").strip(); email=request.form.get("email","").strip()
            if not nome or not cpf:
                flash("Informe nome e CPF.","danger")
            else:
                encrypted=fernet.encrypt(cpf.encode()).decode()
                if rid:
                    con.execute("UPDATE tutores SET nome=?,cpf_cifrado=?,telefone=?,email=? WHERE id=?",(nome,encrypted,telefone,email,rid))
                else:
                    con.execute("INSERT INTO tutores(nome,cpf_cifrado,telefone,email) VALUES(?,?,?,?)",(nome,encrypted,telefone,email))
                flash("Tutor salvo com sucesso.","success")
            return redirect(url_for("tutores"))
        term=request.args.get("q","").strip()
        rows=con.execute("SELECT * FROM tutores WHERE nome LIKE ? ORDER BY nome",(f"%{term}%",)).fetchall()
        data=[]
        for r in rows:
            try: cpf=fernet.decrypt(r["cpf_cifrado"].encode()).decode()
            except (InvalidToken, ValueError): cpf="[indisponível]"
            data.append(dict(id=r["id"],nome=r["nome"],cpf=cpf,telefone=r["telefone"],email=r["email"]))
    return render_template("tutores.html", rows=data, q=term)

@app.route("/tutores/excluir/<int:rid>", methods=["POST"])
@login_required
def excluir_tutor(rid):
    try:
        with db() as con: con.execute("DELETE FROM tutores WHERE id=?",(rid,))
        flash("Tutor excluído.","success")
    except sqlite3.IntegrityError:
        flash("Não é possível excluir: há pets ou agendamentos vinculados a este tutor.","danger")
    return redirect(url_for("tutores"))

@app.route("/pets", methods=["GET","POST"])
@login_required
def pets():
    with db() as con:
        if request.method=="POST":
            rid=request.form.get("id"); nome=request.form.get("nome","").strip()
            especie=request.form.get("especie","").strip(); raca=request.form.get("raca","").strip()
            idade=request.form.get("idade","").strip(); tutor_id=request.form.get("tutor_id","")
            try:
                if not nome or not especie or not tutor_id: raise ValueError()
                idade_num=int(idade) if idade else None
                if idade_num is not None and idade_num<0: raise ValueError()
                if rid:
                    con.execute("UPDATE pets SET nome=?,especie=?,raca=?,idade=?,tutor_id=? WHERE id=?",(nome,especie,raca,idade_num,tutor_id,rid))
                else:
                    con.execute("INSERT INTO pets(nome,especie,raca,idade,tutor_id) VALUES(?,?,?,?,?)",(nome,especie,raca,idade_num,tutor_id))
                flash("Pet salvo com sucesso.","success")
            except (ValueError, sqlite3.IntegrityError):
                flash("Confira nome, espécie, idade e tutor responsável.","danger")
            return redirect(url_for("pets"))
        term=request.args.get("q","").strip()
        tutors=con.execute("SELECT id,nome FROM tutores ORDER BY nome").fetchall()
        rows=[dict(r) for r in con.execute("""SELECT p.*,t.nome AS tutor FROM pets p JOIN tutores t ON t.id=p.tutor_id
                            WHERE p.nome LIKE ? ORDER BY p.nome""",(f"%{term}%",)).fetchall()]
    return render_template("pets.html",rows=rows,tutors=tutors,q=term)

@app.route("/pets/excluir/<int:rid>", methods=["POST"])
@login_required
def excluir_pet(rid):
    try:
        with db() as con: con.execute("DELETE FROM pets WHERE id=?",(rid,))
        flash("Pet excluído.","success")
    except sqlite3.IntegrityError:
        flash("Não é possível excluir: há agendamentos vinculados a este pet.","danger")
    return redirect(url_for("pets"))

@app.route("/agendamentos", methods=["GET","POST"])
@login_required
def agendamentos():
    with db() as con:
        if request.method=="POST":
            rid=request.form.get("id"); data=request.form.get("data_hora","").strip()
            motivo=request.form.get("motivo","").strip(); status=request.form.get("status","Agendado")
            tutor_id=request.form.get("tutor_id",""); pet_id=request.form.get("pet_id","")
            try:
                dt=datetime.strptime(data,"%Y-%m-%dT%H:%M").strftime("%Y-%m-%d %H:%M")
                pet=con.execute("SELECT id FROM pets WHERE id=? AND tutor_id=?",(pet_id,tutor_id)).fetchone()
                if not motivo or not pet: raise ValueError()
                if rid:
                    con.execute("UPDATE agendamentos SET data_hora=?,motivo=?,status=?,tutor_id=?,pet_id=? WHERE id=?",(dt,motivo,status,tutor_id,pet_id,rid))
                else:
                    con.execute("INSERT INTO agendamentos(data_hora,motivo,status,tutor_id,pet_id) VALUES(?,?,?,?,?)",(dt,motivo,status,tutor_id,pet_id))
                flash("Agendamento salvo com sucesso.","success")
            except (ValueError, sqlite3.IntegrityError):
                flash("Confira data, motivo, tutor e pet correspondente.","danger")
            return redirect(url_for("agendamentos"))
        term=request.args.get("q","").strip()
        tutors=con.execute("SELECT id,nome FROM tutores ORDER BY nome").fetchall()
        pets_rows=con.execute("SELECT id,nome,tutor_id FROM pets ORDER BY nome").fetchall()
        rows=[dict(r) for r in con.execute("""SELECT a.*,t.nome AS tutor,p.nome AS pet FROM agendamentos a
            JOIN tutores t ON t.id=a.tutor_id JOIN pets p ON p.id=a.pet_id
            WHERE a.data_hora LIKE ? OR a.motivo LIKE ? OR t.nome LIKE ? OR p.nome LIKE ?
            ORDER BY a.data_hora""",(f"%{term}%",)*4).fetchall()]
    return render_template("agendamentos.html",rows=rows,tutors=tutors,pets=pets_rows,q=term)

@app.route("/agendamentos/excluir/<int:rid>", methods=["POST"])
@login_required
def excluir_agendamento(rid):
    with db() as con: con.execute("DELETE FROM agendamentos WHERE id=?",(rid,))
    flash("Agendamento excluído.","success")
    return redirect(url_for("agendamentos"))

@app.context_processor
def inject_globals():
    return {"current_user":session.get("nome")}

init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=False)
