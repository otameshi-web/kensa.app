import bcrypt

password = "nihonev1215" # パスワードを入れる
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print(hashed.decode())
