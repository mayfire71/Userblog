# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import jinja2
import webapp2
import re 
import hashlib
import hmac
from string import letters
import random 

from google.appengine.ext import db 


template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment ( loader = jinja2.FileSystemLoader(template_dir))

secret = "a"



def render_str(self, template, **params):
		t=jinja_env.get_template(template)
		return t.render(params)

def make_secure_val(val):
	return '%s|%s' %(val,hmac.new(secret,val).hexdigest())

def check_secure_val(secure_val):
	val = secure_val.split('|')[0]
	if secure_val == make_secure_val(val):
		return val




class Handler(webapp2.RequestHandler):
	def write (self, *a , **kw):
		self.response.out.write(*a, **kw)

	def render_str(self, template, **params):
		t=jinja_env.get_template(template)
		return t.render(params)
	
	def render(self, template, **kw):
		self.write(self.render_str(template, **kw))

	def set_secure_cookie(self,name,val):
		cookie_val = make_secure_val(val)
		self.response.headers.add_header('Set-Cookie', '%s=%s; Path=/' % (name, cookie_val))

	def read_secure_cookie(self,name):
		cookie_val = self.request.cookies.get(name)
		return cookie_val and check_secure_val(cookie_val)

	def login(self,user):
		self.set_secure_cookie('user_id',str(user.key().id()))
	def logout (self):
		self.response.headers.add_header('set-cookie', 'user_id=; path =/')

	def initialize (self, *a , **kw):
		webapp2.RequestHandler.initialize(self, *a ,**kw)
		uid = self.read_secure_cookie('user_id')
		self.user = uid and User.by_id(int(uid))

	# def set_cookie(self,name, val):
	#     self.response.headers.add_header('Set-Cookie','%s=%s; Path=/' % (name, val))

def make_salt(length=5):
	return ''.join(random.choice(letters) for x in range(length))
	

def valid_pw(name,password,h):
	salt = h.split(',')[0]
	return h == make_pw_hash(name, password, salt)

def users_key(group ='default'):
	return db.Key.from_path('users',group)

def make_pw_hash(name,pw,salt=None):
	if not salt:
		salt = make_salt()
	h = hashlib.sha256(name+pw+salt).hexdigest()
	return '%s,%s'% (salt,h)

class User(db.Model):
	name = db.StringProperty(required = True)
	pw_hash = db.StringProperty(required = True)
	email = db.StringProperty()

	@classmethod
	def by_id(cls,uid):
		return User.get_by_id(uid,parent = users_key())

	@classmethod
	def by_name(cls,name):
		u = User.all().filter('name =',name).get()
		return u 

	@classmethod
	def register(cls,name,pw,email = None):
		pw_hash = make_pw_hash(name,pw)
		return User(parent=users_key(), name = name , pw_hash = pw_hash, email = email)

	@classmethod
	def login2(cls,name,pw):
		u = cls.by_name(name)
		if u and valid_pw(name, pw, u.pw_hash):
			return u 

class comment(db.Model):
	content = db.TextProperty(required = True)
	blogid = db.IntegerProperty(required = True )	
	userid = db.StringProperty(required = False)
	created = db.DateTimeProperty(auto_now_add = True)

class blog(db.Model):
	title = db.StringProperty(required = True)
	content = db.TextProperty( required = True)
	created = db.DateTimeProperty(auto_now_add = True)
	author = db.StringProperty(required = False)
	user_name = db.StringProperty(required = False)
	likes = db.IntegerProperty(required = False)

class likes(db.Model):
	blogid = db.IntegerProperty(required = True)
	userid = db.StringProperty(required = True)



USER_RE = re.compile (r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
	return username and USER_RE.match(username)
PASS_RE =re.compile(r"^.{3,20}$")
def valid_password (password):
	return password and PASS_RE.match(password)
EMAIL_RE = re.compile (r"^[\S]+@[\S]+\.[\S]+$")
def valid_email(email):
	return  not email or EMAIL_RE.match(email) 


#class for the main signup and insuring user info is valid  
class Signup(Handler):
	def get(self):
		self.render("index.html")

	def post(self):
		have_error = False 
		self.username =self.request.get('username')
		self.password = self.request.get('password')
		self.verify = self.request.get('verify')
		self.email = self.request.get('email')

		params = dict(username = self.username , email = self.email)

		if not valid_username(self.username):
			params['error_username'] = " Invalid username."
			have_error = True

		if not valid_password(self.password):
			params ['error_password'] = "That is not a valid password "
			have_error = True

		elif self.password != self.verify:
			params['error_verify'] = "The passwords did not match!"
			have_error = True

		if not valid_email(self.email):
			params['error_email'] = "That is not a valid email"
			have_error = True 

		if have_error == True:
			self.render('index.html',**params)
		else: 
			self.done()

	def done(self):
		u = User.by_name(self.username)
		if u :
			msg = 'Username has already been taken'
			self.render('index.html', error_username = msg)
		else:
			u = User.register(self.username,self.password,self.email)
			u.put()

			self.login(u)
			self.redirect('/mainpage')

class Login(Handler):
	def get(self):
		self.render('login.html')

	def post(self):
		username= self.request.get('username')
		password = self.request.get('password')

		u = User.login2(username,password)
		if u:
			self.login(u)
			self.redirect('/mainpage')
		else:
			msg = 'invalid login'
			self.render('login.html', error = msg)

class Mainpage(Handler):
	def get(self):
		if self.user:
			Blogs = db.GqlQuery("SELECT * FROM blog ""ORDER BY created DESC ")
			self.render("mainpage.html",Blogs = Blogs ,  username = self.user.name  )
		else:
		 	self.redirect('/signup')
class like(Handler):
	def get(self,blog_id):
		cookie_author = check_secure_val(self.request.cookies.get('user_id'))
		s= blog.get_by_id(int(blog_id))
		q = s.key().id()
		if s :
			if cookie_author != s.author:
				liking = db.GqlQuery("SELECT * FROM likes WHERE blogid = :ss and userid = :k", ss=q,k=cookie_author)
				liking = liking.fetch(1)
				if liking == []:
					p = likes(userid = cookie_author, blogid = q)
					p.put()
					updated_likes= s.likes +1
					s.likes = updated_likes
					s.put()
					self.redirect('/mainpage')
				else:
					u = likes.all().filter('userid =',cookie_author).filter('blogid =',q).get()
					updated_likes= s.likes - 1
					s.likes = updated_likes
					s.put()
					u.delete()
					self.redirect('/mainpage')
			else:
				self.write('You cant like your own post ')
		else:
			self.write('Error 404 Page not Found')

class Logout(Handler):
	def get(self):
		self.logout()
		self.redirect('/signup')

#class to display the new post page 
class Newpost(Handler):
	def get(self):
		author = check_secure_val(self.request.cookies.get('user_id'))
		if author:
			self.render('newpost.html')
		else:
			self.redirect('/login')

	def post (self):
		if self.user:
			title = self.request.get('title')
			content = self.request.get('content')
			author = check_secure_val(self.request.cookies.get('user_id'))
			user_name = self.user.name
			likes = 0 
			u = User.all().filter('name =',user_name).get()
			print(u)
			if u:
				if title and content:
					Blog=blog(title =title, content = content, author = author, user_name = user_name, likes = likes)
					key= Blog.put()
					self.redirect("/blog/%d" %key.id())
				else:
					self.render("newpost.html")
			else:
				self.redirect('/login')
		else:
			self.redirect('/login')

class blog_single(Handler):
	def get(self, blog_id):
		key = db.Key.from_path('blog', int(blog_id))
		post = db.get(key)
		if not post:
			return self.redirect('/mainpage')

        	Blog = blog.get_by_id(int(blog_id))
        	s = Blog.key().id()
        	Comments = db.GqlQuery("SELECT * FROM comment WHERE blogid = :ss", ss=s)
        	self.render("blog.html", Blogs = [Blog], Comments = Comments)

	def post(self,blog_id):
		s= blog.get_by_id(int(blog_id))
		# t = check_secure_val(self.request.cookies.get('user_id'))
		content = self.request.get('content')
		un = self.user.name
		if s:
			if content:
				Comment = comment(content= content, blogid = s.key().id(), userid = un)
				Comment.put()
				self.redirect("/blog/%d" %s.key().id())
			else:
				self.redirect("/mainpage")
		else:
			self.redirect("/mainpage")

class edit_comment(Handler):
	def get(self,comment_id):
		s= comment.get_by_id(int(comment_id))
		t = check_secure_val(self.request.cookies.get('user_id'))
		if s :
			if t:
				if s.userid == self.user.name:
					self.render("edit_comment.html", Comments = [s])
				else:
					self.redirect('/mainpage')
			else:
				self.redirect('/mainpage')
		else:
			self.redirect('/mainpage')

	def post(self,comment_id):
		s= comment.get_by_id(int(comment_id))
		if s:
			u = s.key().id()
			t = self.user.name
			y = s.blogid
			if t == s.userid and u == int(comment_id):
				content = self.request.get('content')
				s.content = content
				s.put()
				self.redirect('/blog/%d'%y)
			else:
				self.redirect('/blog/%d'%y)
		else:
			self.redirect('/mainpage')

class delete_comment(Handler):
	def get(self,comment_id):
		s= comment.get_by_id(int(comment_id))
		if self.user and s:
			t = check_secure_val(self.request.cookies.get('user_id'))
			if s.userid == self.user.name:
				self.render("delete_comment.html", Comments = [s])
			else:
				self.redirect('/mainpage')

	def post(self,comment_id):
		s= comment.get_by_id(int(comment_id))
		if self.user and s:
			u = s.blogid
			if s.userid == self.user.name:
				s.delete()
				self.redirect('/blog/%d'%u)
			else:
				self.redirect('/blog/%d'%u)
		else:
			self.redirect('/blog/%d'%u)

class delete_post(Handler):
	def get(self, blog_id):
		Blog = blog.get_by_id(int(blog_id))
		cookie_author = check_secure_val(self.request.cookies.get('user_id'))

		if self.user and Blog:
			if Blog.author == cookie_author:
				self.render("delete.html", Blogs = [Blog])

			else:
				self.redirect('/blog/%d'%blog_id)
		else:
			self.redirect('/blog/%d'%blog_id)

	def post(self,blog_id):
		cookie_author = check_secure_val(self.request.cookies.get('user_id'))
		s= blog.get_by_id(int(blog_id))
		if self.user and s:
			if s.author == cookie_author:
				s.delete()
				self.redirect("/mainpage")

			else:
				self.redirect("/mainpage")
		else:
			self.redirect("/mainpage")

class edit_post(Handler):
	def get(self, blog_id):
		cookie_author = check_secure_val(self.request.cookies.get('user_id'))
		Blog = blog.get_by_id(int(blog_id))
		if self.user and Blog:
			if Blog.author == cookie_author:
				self.render("edit.html", Blogs = [Blog])

			else:
				self.redirect('/mainpage')
		else:
			self.redirect('/mainpage')

	def post(self,blog_id):
		cookie_author = check_secure_val(self.request.cookies.get('user_id'))
		s= blog.get_by_id(int(blog_id))
		if self.user and s:
			if s.author == cookie_author:

				title = self.request.get('title')
				content = self.request.get('content')
				author = check_secure_val(self.request.cookies.get('user_id'))
				
				s= blog.get_by_id(int(blog_id))
				s.title = title
				s.content = content
				s.author = author
				s.put()
				self.render("blog.html", Blogs = [s])

			else:
				self.redirect("/mainpage")

		else:
			self.redirect('/mainpage')

app = webapp2.WSGIApplication([ ('/newpost',Newpost),
	('/blog/(\d+)', blog_single), 
	("/login", Login), 
	("/like/(\d+)", like), 
	('/signup', Signup), 
	('/login',Login), 
	('/logout',Logout), 
	('/mainpage',Mainpage),
	('/delete/(\d+)',delete_post),
	('/edit_comment/(\d+)',edit_comment),
	('/delete_comment/(\d+)',delete_comment),
	('/edit/(\d+)',edit_post)],debug=True)



