import os
import atexit
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from jinja2 import ChoiceLoader, FileSystemLoader, DictLoader
from apscheduler.schedulers.background import BackgroundScheduler

import db
import drive_handler
import instagram_bot

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

# Embedded Fallback Templates (Ensures the app NEVER crashes even if HTML files are missing on GitHub)
FALLBACK_TEMPLATES = {
    "base.html": """<!DOCTYPE html>
<html lang="bn" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Instagram Auto Scheduler{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        brand: {
                            pink: '#E1306C',
                            purple: '#833AB4',
                            orange: '#F77737'
                        }
                    }
                }
            }
        }
    </script>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen flex flex-col font-sans">
    <nav class="bg-gray-800/80 backdrop-blur border-b border-gray-700 sticky top-0 z-50">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex items-center justify-between h-16">
                <a href="{{ url_for('index') }}" class="flex items-center space-x-3">
                    <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-yellow-400 via-pink-600 to-purple-700 flex items-center justify-center shadow-lg shadow-pink-500/20">
                        <i class="fab fa-instagram text-white text-2xl"></i>
                    </div>
                    <div>
                        <span class="font-bold text-lg bg-gradient-to-r from-pink-500 to-purple-400 bg-clip-text text-transparent">InstaSchedule</span>
                        <span class="text-xs block text-gray-400 font-mono">Auto 3H Poster</span>
                    </div>
                </a>

                <div class="flex items-center space-x-3">
                    <a href="{{ url_for('index') }}" class="px-3 py-2 text-sm font-medium rounded-lg hover:bg-gray-700 text-gray-300 hover:text-white transition">
                        <i class="fas fa-th-list mr-1"></i> ড্যাশবোর্ড
                    </a>
                    <a href="{{ url_for('health') }}" target="_blank" class="px-3 py-2 text-xs font-mono rounded-lg bg-green-950/60 text-green-400 border border-green-800/50 flex items-center gap-1.5" title="UptimeRobot এ এই লিঙ্কটি পিং করাবেন">
                        <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                        /health
                    </a>
                </div>
            </div>
        </div>
    </nav>

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 mt-4 w-full">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    {% set bg = 'bg-blue-900/60 border-blue-500 text-blue-200' %}
                    {% if category == 'success' %}
                        {% set bg = 'bg-green-900/60 border-green-500 text-green-200' %}
                    {% elif category == 'danger' %}
                        {% set bg = 'bg-red-900/60 border-red-500 text-red-200' %}
                    {% elif category == 'warning' %}
                        {% set bg = 'bg-yellow-900/60 border-yellow-500 text-yellow-200' %}
                    {% endif %}
                    <div class="p-4 mb-3 rounded-xl border {{ bg }} flex items-center justify-between text-sm shadow">
                        <div class="flex items-center space-x-2">
                            <i class="fas fa-info-circle"></i>
                            <span>{{ message }}</span>
                        </div>
                        <button onclick="this.parentElement.remove()" class="text-gray-400 hover:text-white">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
    </div>

    <main class="flex-grow max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full">
        {% block content %}{% endblock %}
    </main>

    <footer class="bg-gray-800/50 border-t border-gray-800 py-4 text-center text-xs text-gray-500">
        <p>Instagram Auto Post Scheduler • Render + UptimeRobot 24/7 Free Setup</p>
    </footer>
</body>
</html>""",

    "dashboard.html": """{% extends "base.html" %}

{% block title %}Dashboard - Instagram Auto Scheduler{% endblock %}

{% block content %}
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

    <!-- Left Column: Instagram Status & Add Post Form -->
    <div class="lg:col-span-1 space-y-6">

        <!-- Instagram Connection Card -->
        <div class="bg-gray-800 border border-gray-700/80 rounded-2xl p-5 shadow-lg">
            <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4 flex items-center justify-between">
                <span>Instagram Status</span>
                <i class="fab fa-instagram text-pink-500"></i>
            </h2>

            {% if login_info.logged_in %}
                <div class="flex items-center justify-between p-3.5 bg-gray-900/60 rounded-xl border border-green-500/30">
                    <div class="flex items-center space-x-3">
                        <div class="w-10 h-10 rounded-full bg-gradient-to-tr from-pink-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow">
                            {{ login_info.username[0]|upper }}
                        </div>
                        <div>
                            <p class="font-bold text-white text-sm">@{{ login_info.username }}</p>
                            <span class="inline-flex items-center text-xs text-green-400 font-medium">
                                <span class="w-1.5 h-1.5 rounded-full bg-green-400 mr-1.5 animate-pulse"></span>
                                কানেক্টেড আছে
                            </span>
                        </div>
                    </div>
                    <form action="{{ url_for('logout') }}" method="POST">
                        <button type="submit" class="px-2.5 py-1.5 text-xs text-red-400 hover:text-red-300 hover:bg-red-950/40 rounded-lg transition" title="Log Out">
                            <i class="fas fa-sign-out-alt"></i> লগআউট
                        </button>
                    </form>
                </div>
            {% else %}
                <div class="p-4 bg-red-950/30 border border-red-800/40 rounded-xl text-center">
                    <div class="w-12 h-12 rounded-full bg-red-900/40 text-red-400 flex items-center justify-center mx-auto mb-2 text-xl">
                        <i class="fas fa-user-lock"></i>
                    </div>
                    <p class="text-sm text-gray-300 font-medium mb-1">কোনো অ্যাকাউন্ট লগইন নেই</p>
                    <p class="text-xs text-gray-400 mb-3">পোস্ট করার পূর্বে ওয়েবসাইটে ইনস্টাগ্রাম লগইন করুন।</p>
                    <a href="{{ url_for('login') }}" class="w-full inline-flex items-center justify-center px-4 py-2 bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white rounded-xl text-sm font-semibold shadow-md transition">
                        <i class="fab fa-instagram mr-2"></i> লগইন করুন
                    </a>
                </div>
            {% endif %}
        </div>

        <!-- Add Post Form -->
        <div class="bg-gray-800 border border-gray-700/80 rounded-2xl p-5 shadow-lg">
            <h2 class="text-base font-bold text-white mb-4 flex items-center">
                <i class="fas fa-plus-circle text-pink-500 mr-2"></i>
                নতুন পোস্ট শিডিউল করুন
            </h2>

            <form action="{{ url_for('add_new_post') }}" method="POST" class="space-y-4">
                <!-- Google Drive URL -->
                <div>
                    <label class="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1">
                        Google Drive লিঙ্ক <span class="text-red-400">*</span>
                    </label>
                    <input type="url" name="drive_url" required
                           placeholder="https://drive.google.com/file/d/.../view"
                           class="w-full px-3.5 py-2.5 bg-gray-900 border border-gray-700 rounded-xl text-sm text-white focus:outline-none focus:border-pink-500 focus:ring-1 focus:ring-pink-500 transition">
                    <p class="text-[11px] text-gray-400 mt-1 flex items-start gap-1">
                        <i class="fas fa-info-circle text-blue-400 mt-0.5"></i>
                        <span>ড্রাইভ ফাইলটি অবশ্যই <strong>"Anyone with the link"</strong> পাবলিক ভিউয়ার থাকতে হবে। ইমেজ বা ভিডিও (Reels) দুই-ই দিতে পারবেন।</span>
                    </p>
                </div>

                <!-- Title -->
                <div>
                    <label class="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1">
                        টাইটেল (ঐচ্ছিক)
                    </label>
                    <input type="text" name="title"
                           placeholder="যেমন: আজকের বিশেষ মুহূর্ত"
                           class="w-full px-3.5 py-2 bg-gray-900 border border-gray-700 rounded-xl text-sm text-white focus:outline-none focus:border-pink-500 transition">
                </div>

                <!-- Caption -->
                <div>
                    <label class="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1">
                        ক্যাপশন
                    </label>
                    <textarea name="caption" rows="3"
                              placeholder="আপনার পোস্টের বিস্তারিত ক্যাপশন লিখুন..."
                              class="w-full px-3.5 py-2 bg-gray-900 border border-gray-700 rounded-xl text-sm text-white focus:outline-none focus:border-pink-500 transition"></textarea>
                </div>

                <!-- Hashtags -->
                <div>
                    <label class="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1">
                        হ্যাশট্যাগ (#)
                    </label>
                    <input type="text" name="hashtags"
                           placeholder="#reels #explore #viral #instagram"
                           class="w-full px-3.5 py-2 bg-gray-900 border border-gray-700 rounded-xl text-sm text-white focus:outline-none focus:border-pink-500 transition">
                </div>

                <!-- Submit Button -->
                <button type="submit" class="w-full py-2.5 bg-gradient-to-r from-pink-600 via-purple-600 to-indigo-600 hover:opacity-95 text-white font-semibold rounded-xl text-sm shadow-lg shadow-pink-500/20 transition flex items-center justify-center space-x-2">
                    <i class="fas fa-calendar-plus"></i>
                    <span>কিউ-তে যুক্ত করুন</span>
                </button>
            </form>
        </div>

        <!-- 24/7 Keep-Alive UptimeRobot Helper -->
        <div class="bg-gray-800/60 border border-gray-700/60 rounded-2xl p-4 text-xs space-y-2 text-gray-300">
            <div class="flex items-center text-green-400 font-semibold gap-1.5">
                <i class="fas fa-robot"></i>
                <span>UptimeRobot ২৪/৭ সেটআপ গাইড</span>
            </div>
            <p>আপনার Render সার্ভার যেন কখনো না ঘুমায়, সেজন্য <strong>UptimeRobot.com</strong>-এ গিয়ে একটি <strong>HTTP(s) Monitor</strong> তৈরি করুন এবং নিচের ইউআরএলটি প্রতি ৫ মিনিটে পিং করাতে দিন:</p>
            <div class="bg-gray-900 p-2 rounded-lg font-mono text-[11px] text-pink-400 break-all select-all border border-gray-700">
                https://&lt;আপনার-রেন্ডার-অ্যাপ&gt;.onrender.com/health
            </div>
        </div>

    </div>

    <!-- Right Column: Schedule Queue & Post List -->
    <div class="lg:col-span-2 space-y-6">

        <!-- Status & Next Run Banner -->
        <div class="bg-gradient-to-r from-gray-800 to-gray-800/90 border border-gray-700 rounded-2xl p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
                <div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-purple-400 mb-1">
                    <i class="fas fa-clock"></i>
                    <span>শিডিউল টাইম: প্রতি {{ interval_hours }} ঘণ্টা পরপর</span>
                </div>
                <h3 class="text-base font-bold text-white">
                    {% if next_post %}
                        পরবর্তী পোস্ট: <span class="text-pink-400">#{{ next_post.id }} ({{ next_post.title or 'অপেক্ষমাণ' }})</span>
                    {% else %}
                        বর্তমানে কোনো পোস্ট কিউ-তে নেই
                    {% endif %}
                </h3>
            </div>

            {% if next_post %}
                <form action="{{ url_for('post_now', post_id=next_post.id) }}" method="POST">
                    <button type="submit" class="px-4 py-2 bg-pink-600 hover:bg-pink-500 text-white text-xs font-semibold rounded-xl shadow-md flex items-center gap-1.5 transition">
                        <i class="fas fa-paper-plane"></i>
                        <span>এখনই পোস্ট করুন</span>
                    </button>
                </form>
            {% endif %}
        </div>

        <!-- Post Queue Table -->
        <div class="bg-gray-800 border border-gray-700/80 rounded-2xl overflow-hidden shadow-lg">
            <div class="px-5 py-4 border-b border-gray-700/80 flex items-center justify-between">
                <h3 class="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                    <i class="fas fa-list-ol text-pink-500"></i>
                    <span>পোস্টের তালিকা (Queue) [{{ posts|length }}]</span>
                </h3>
            </div>

            {% if posts %}
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm text-gray-300">
                        <thead class="bg-gray-900/60 text-xs uppercase font-semibold text-gray-400 border-b border-gray-700">
                            <tr>
                                <th class="px-4 py-3">#ID</th>
                                <th class="px-4 py-3">মিডিয়া</th>
                                <th class="px-4 py-3">ক্যাপশন ও হ্যাশট্যাগ</th>
                                <th class="px-4 py-3">স্ট্যাটাস</th>
                                <th class="px-4 py-3 text-right">অ্যাকশন</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-700/60 font-normal">
                            {% for post in posts %}
                                <tr class="hover:bg-gray-750/50 transition">
                                    <td class="px-4 py-3.5 font-mono text-xs text-gray-400">
                                        #{{ post.id }}
                                    </td>
                                    <td class="px-4 py-3.5">
                                        <a href="{{ post.drive_url }}" target="_blank" class="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 underline font-mono">
                                            <i class="fab fa-google-drive"></i>
                                            <span>ড্রাইভ ফাইল</span>
                                        </a>
                                        {% if post.media_type %}
                                            <span class="block text-[10px] text-gray-500 uppercase">{{ post.media_type }}</span>
                                        {% endif %}
                                    </td>
                                    <td class="px-4 py-3.5 max-w-xs">
                                        {% if post.title %}
                                            <p class="font-semibold text-white text-xs truncate">{{ post.title }}</p>
                                        {% endif %}
                                        <p class="text-xs text-gray-300 line-clamp-2">{{ post.caption or '—' }}</p>
                                        {% if post.hashtags %}
                                            <p class="text-[11px] text-pink-400 truncate mt-0.5">{{ post.hashtags }}</p>
                                        {% endif %}
                                    </td>
                                    <td class="px-4 py-3.5 whitespace-nowrap">
                                        {% if post.status == 'pending' %}
                                            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-yellow-950/60 text-yellow-400 border border-yellow-700/50">
                                                <i class="fas fa-hourglass-start mr-1"></i> অপেক্ষমাণ
                                            </span>
                                        {% elif post.status == 'processing' %}
                                            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-950/60 text-indigo-400 border border-indigo-700/50">
                                                <i class="fas fa-spinner fa-spin mr-1"></i> আপলোড হচ্ছে...
                                            </span>
                                        {% elif post.status == 'posted' %}
                                            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-green-950/60 text-green-400 border border-green-700/50" title="{{ post.posted_at }}">
                                                <i class="fas fa-check-circle mr-1"></i> সফলভাবে পোস্ট হয়েছে
                                            </span>
                                        {% elif post.status == 'failed' %}
                                            <div>
                                                <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-950/60 text-red-400 border border-red-700/50">
                                                    <i class="fas fa-exclamation-triangle mr-1"></i> ব্যর্থ
                                                </span>
                                                {% if post.error_message %}
                                                    <p class="text-[10px] text-red-300 mt-1 max-w-[150px] truncate" title="{{ post.error_message }}">{{ post.error_message }}</p>
                                                {% endif %}
                                            </div>
                                        {% endif %}
                                    </td>
                                    <td class="px-4 py-3.5 text-right whitespace-nowrap">
                                        <div class="flex items-center justify-end space-x-2">
                                            {% if post.status != 'posted' %}
                                                <form action="{{ url_for('post_now', post_id=post.id) }}" method="POST">
                                                    <button type="submit" class="p-1.5 text-xs bg-pink-600/20 hover:bg-pink-600/40 text-pink-300 rounded-lg transition" title="এখনই পোস্ট করুন">
                                                        <i class="fas fa-play"></i>
                                                    </button>
                                                </form>
                                            {% endif %}
                                            <form action="{{ url_for('delete_post_route', post_id=post.id) }}" method="POST" onsubmit="return confirm('আপনি কি এই পোস্টটি মুছে ফেলতে চান?')">
                                                <button type="submit" class="p-1.5 text-xs bg-red-950/30 hover:bg-red-950/60 text-red-400 rounded-lg transition" title="মুছে ফেলুন">
                                                    <i class="fas fa-trash-alt"></i>
                                                </button>
                                            </form>
                                        </div>
                                    </td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            {% else %}
                <div class="p-8 text-center text-gray-400">
                    <i class="fas fa-inbox text-4xl mb-3 text-gray-600"></i>
                    <p class="text-sm">বর্তমানে কোনো শিডিউল পোস্ট নেই।</p>
                    <p class="text-xs text-gray-500 mt-1">বাম পাশের ফর্ম থেকে আপনার গুগল ড্রাইভ লিঙ্ক দিয়ে প্রথম পোস্টটি যোগ করুন।</p>
                </div>
            {% endif %}
        </div>

    </div>

</div>
{% endblock %}""",

    "login.html": """{% extends "base.html" %}

{% block title %}Instagram Login - Auto Scheduler{% endblock %}

{% block content %}
<div class="max-w-lg mx-auto py-6">
    <div class="bg-gray-800 border border-gray-700 rounded-3xl p-6 sm:p-8 shadow-2xl relative overflow-hidden">
        <div class="absolute -top-12 -right-12 w-32 h-32 bg-pink-600/20 rounded-full blur-2xl pointer-events-none"></div>
        <div class="absolute -bottom-12 -left-12 w-32 h-32 bg-purple-600/20 rounded-full blur-2xl pointer-events-none"></div>

        <div class="text-center mb-6">
            <div class="w-14 h-14 rounded-2xl bg-gradient-to-tr from-yellow-400 via-pink-600 to-purple-700 flex items-center justify-center mx-auto mb-3 shadow-lg shadow-pink-500/20">
                <i class="fab fa-instagram text-white text-2xl"></i>
            </div>
            <h2 class="text-xl font-bold text-white">ইনস্টাগ্রাম লগইন</h2>
            <p class="text-xs text-gray-400 mt-1">পাসওয়ার্ড অথবা কুকিজ (Cookies) দিয়ে সহজে কানেক্ট করুন</p>
        </div>

        <div class="flex p-1 bg-gray-900 rounded-xl mb-6 border border-gray-700/80">
            <button type="button" id="tab-btn-cookie" onclick="switchTab('cookie')"
                    class="flex-1 py-2 text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 {% if active_tab == 'cookie' or not active_tab %}bg-pink-600 text-white shadow{% else %}text-gray-400 hover:text-white{% endif %}">
                <i class="fas fa-cookie-bite text-yellow-400"></i>
                <span>Cookies দিয়ে (সুপার ফাস্ট ⭐)</span>
            </button>
            <button type="button" id="tab-btn-password" onclick="switchTab('password')"
                    class="flex-1 py-2 text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 {% if active_tab == 'password' %}bg-pink-600 text-white shadow{% else %}text-gray-400 hover:text-white{% endif %}">
                <i class="fas fa-key"></i>
                <span>ইউজারনেম ও পাসওয়ার্ড</span>
            </button>
        </div>

        <!-- 1. Cookie Login Form -->
        <div id="tab-content-cookie" class="{% if active_tab == 'password' %}hidden{% endif %} space-y-4">
            <div class="p-3.5 bg-gray-900/80 rounded-xl border border-gray-700 text-xs space-y-2 text-gray-300">
                <p class="font-semibold text-yellow-400 flex items-center gap-1">
                    <i class="fas fa-magic"></i>
                    <span>কুকিজ দিয়ে লগইনের সুবিধা:</span>
                </p>
                <p class="text-[11px] leading-relaxed text-gray-400">
                    কোনো পাসওয়ার্ড বা ওটিপির ঝামেলা নেই। এটি ১০০% নিশ্চিতভাবে কাজ করে এবং ১ সেকেন্ডে ইনস্ট্যান্ট লগইন হয়ে যায়।
                </p>
                <div class="pt-2 border-t border-gray-800 text-[11px] space-y-1 text-gray-400">
                    <p class="font-medium text-gray-300">💡 যেভাবে <code class="text-pink-400 font-mono">sessionid</code> কপি করবেন:</p>
                    <ol class="list-decimal list-inside space-y-0.5 pl-1">
                        <li>ব্রাউজারে <a href="https://instagram.com" target="_blank" class="text-blue-400 underline">instagram.com</a>-এ লগইন করুন।</li>
                        <li>কিবোর্ডে <kbd class="px-1 py-0.5 bg-gray-800 border border-gray-600 rounded text-[10px]">F12</kbd> চাপুন ➔ <strong>Application</strong> (বা Storage) ট্যাবে যান।</li>
                        <li>বামে <strong>Cookies</strong> ➔ <code>https://www.instagram.com</code> এ ক্লিক করুন।</li>
                        <li>তালিকায় <strong><span class="text-pink-300">sessionid</span></strong>-এর মানটি (Value) ডাবল ক্লিক করে কপি করুন।</li>
                    </ol>
                </div>
            </div>

            <form action="{{ url_for('login') }}" method="POST" class="space-y-4" onsubmit="var btn=document.getElementById('cookie-login-btn'); btn.disabled=true; btn.innerHTML='<i class=\\'fas fa-spinner fa-spin mr-2\\'></i> কানেক্ট হচ্ছে...';">
                <input type="hidden" name="login_type" value="cookie">
                <div>
                    <label class="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1.5">
                        sessionid অথবা সম্পূর্ণ Cookie পেস্ট করুন:
                    </label>
                    <textarea name="cookie_data" required rows="3"
                              placeholder="যেমন: 6928374619%3Adksjdskdsjkdsj... (অথবা Cookie-Editor এর JSON)"
                              class="w-full px-3.5 py-2.5 bg-gray-900 border border-gray-700 rounded-xl text-xs text-white font-mono focus:outline-none focus:border-pink-500 focus:ring-1 focus:ring-pink-500 transition"></textarea>
                </div>

                <button type="submit" id="cookie-login-btn" class="w-full py-3 bg-gradient-to-r from-yellow-500 via-pink-600 to-purple-600 hover:opacity-95 text-white font-semibold rounded-xl text-sm shadow-lg shadow-pink-500/20 transition flex items-center justify-center space-x-2">
                    <i class="fas fa-cookie-bite"></i>
                    <span>কুকিজ দিয়ে ইনস্ট্যান্ট লগইন করুন</span>
                </button>
            </form>
        </div>

        <!-- 2. Password Login Form -->
        <div id="tab-content-password" class="{% if active_tab != 'password' %}hidden{% endif %} space-y-4">
            <form action="{{ url_for('login') }}" method="POST" class="space-y-4" onsubmit="var btn=document.getElementById('pwd-login-btn'); btn.disabled=true; btn.innerHTML='<i class=\\'fas fa-spinner fa-spin mr-2\\'></i> ভেরিফাই হচ্ছে, ২০-৩০ সেকেন্ড অপেক্ষা করুন...';">
                <input type="hidden" name="login_type" value="password">
                
                <div>
                    <label class="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1.5">
                        ইনস্টাগ্রাম ইউজারনেম (ইমেইল নয়, আসল Username দিন)
                    </label>
                    <div class="relative">
                        <span class="absolute inset-y-0 left-0 pl-3.5 flex items-center text-gray-400 text-sm">
                            @
                        </span>
                        <input type="text" name="username" value="{{ username or '' }}" required
                               placeholder="আপনার ইনস্টাগ্রাম Username"
                               class="w-full pl-8 pr-3.5 py-2.5 bg-gray-900 border border-gray-700 rounded-xl text-sm text-white focus:outline-none focus:border-pink-500 focus:ring-1 focus:ring-pink-500 transition">
                    </div>
                </div>

                <div>
                    <label class="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1.5">
                        পাসওয়ার্ড
                    </label>
                    <div class="relative">
                        <span class="absolute inset-y-0 left-0 pl-3.5 flex items-center text-gray-400 text-sm">
                            <i class="fas fa-lock"></i>
                        </span>
                        <input type="password" name="password" {% if not needs_2fa %}required{% endif %}
                               value="{{ password or '' }}"
                               placeholder="••••••••"
                               class="w-full pl-10 pr-3.5 py-2.5 bg-gray-900 border border-gray-700 rounded-xl text-sm text-white focus:outline-none focus:border-pink-500 focus:ring-1 focus:ring-pink-500 transition">
                    </div>
                </div>

                {% if needs_2fa %}
                    <div class="p-3.5 bg-yellow-950/40 border border-yellow-700/50 rounded-xl space-y-2">
                        <label class="block text-xs font-semibold text-yellow-300 uppercase tracking-wider">
                            <i class="fas fa-shield-alt mr-1"></i> 2FA / সিকিউরিটি কোড (SMS বা App)
                        </label>
                        <input type="text" name="verification_code" required autofocus
                               placeholder="যেমন: 123456"
                               class="w-full px-3.5 py-2.5 bg-gray-900 border border-yellow-600 rounded-xl text-sm text-white font-mono tracking-widest text-center focus:outline-none focus:border-yellow-400 transition">
                        <input type="hidden" name="two_factor_identifier" value="{{ two_factor_identifier }}">
                        <p class="text-[11px] text-yellow-200/80">আপনার ফোনে পাঠানো এসএমএস বা Authenticator অ্যাপের ৬ সংখ্যার ওটিপি কোডটি লিখুন।</p>
                    </div>
                {% endif %}

                <button type="submit" id="pwd-login-btn" class="w-full py-3 bg-gradient-to-r from-pink-600 via-purple-600 to-indigo-600 hover:opacity-95 text-white font-semibold rounded-xl text-sm shadow-lg shadow-pink-500/20 transition flex items-center justify-center space-x-2">
                    <i class="fas fa-sign-in-alt"></i>
                    <span>{% if needs_2fa %}ভেরিফাই ও সম্পন্ন করুন{% else %}পাসওয়ার্ড দিয়ে লগইন করুন{% endif %}</span>
                </button>
            </form>
        </div>

        <div class="mt-6 pt-5 border-t border-gray-750 text-center">
            <p class="text-[11px] text-gray-400 leading-relaxed">
                <i class="fas fa-shield-alt text-green-400 mr-1"></i>
                আপনার তথ্য সুরক্ষিত। লগইন সেশনটি শুধুমাত্র আপনার নিজস্ব Render সার্ভারে এনক্রিপ্ট হয়ে সেভ থাকে।
            </p>
            <a href="{{ url_for('index') }}" class="inline-block mt-3 text-xs text-gray-400 hover:text-white transition">
                <i class="fas fa-arrow-left mr-1"></i> ড্যাশবোর্ডে ফিরে যান
            </a>
        </div>
    </div>
</div>

<script>
function switchTab(tab) {
    const cookieTab = document.getElementById('tab-content-cookie');
    const pwdTab = document.getElementById('tab-content-password');
    const btnCookie = document.getElementById('tab-btn-cookie');
    const btnPwd = document.getElementById('tab-btn-password');

    if (tab === 'cookie') {
        cookieTab.classList.remove('hidden');
        pwdTab.classList.add('hidden');
        btnCookie.className = 'flex-1 py-2 text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 bg-pink-600 text-white shadow';
        btnPwd.className = 'flex-1 py-2 text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 text-gray-400 hover:text-white';
    } else {
        pwdTab.classList.remove('hidden');
        cookieTab.classList.add('hidden');
        btnPwd.className = 'flex-1 py-2 text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 bg-pink-600 text-white shadow';
        btnCookie.className = 'flex-1 py-2 text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 text-gray-400 hover:text-white';
    }
}
</script>
{% endblock %}"""
}

app = Flask(__name__)
# Priority Template Loader: loads latest embedded templates first to avoid stale root files!
app.jinja_loader = ChoiceLoader([
    DictLoader(FALLBACK_TEMPLATES),
    FileSystemLoader(TEMPLATE_DIR),
    FileSystemLoader(BASE_DIR)
])
app.secret_key = os.environ.get("SECRET_KEY", "super-secret-key-123456789")

# Initialize SQLite database
db.init_db()

# Interval in hours for automatic posting (default 3 hours)
POSTING_INTERVAL_HOURS = int(os.environ.get("POST_INTERVAL_HOURS", 3))

def process_single_post(post_dict: dict) -> bool:
    """Helper function to execute a single post from drive to instagram."""
    post_id = post_dict['id']
    drive_url = post_dict['drive_url']
    
    # Check login
    status = instagram_bot.check_login_status()
    if not status.get("logged_in"):
        print(f"[Worker] Cannot post ID {post_id}: Instagram not logged in.")
        db.update_post_status(post_id, 'failed', error_message="Instagram account is not logged in.")
        return False
        
    db.update_post_status(post_id, 'processing')
    
    try:
        print(f"[Worker] Downloading Google Drive file for Post #{post_id}...")
        file_path, media_type = drive_handler.download_drive_file(drive_url)
        
        # Build full caption
        caption_parts = []
        if post_dict.get('title'):
            caption_parts.append(post_dict['title'].strip())
        if post_dict.get('caption'):
            caption_parts.append(post_dict['caption'].strip())
        if post_dict.get('hashtags'):
            hashtags = post_dict['hashtags'].strip()
            caption_parts.append(f"\n{hashtags}")
            
        final_caption = "\n\n".join([p for p in caption_parts if p])
        
        print(f"[Worker] Uploading {media_type} to Instagram for Post #{post_id}...")
        instagram_bot.upload_post(file_path, media_type, final_caption)
        
        db.update_post_status(post_id, 'posted', media_type=media_type)
        print(f"[Worker] Post #{post_id} successfully published to Instagram!")
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"[Worker] Error processing Post #{post_id}: {error_msg}")
        db.update_post_status(post_id, 'failed', error_message=error_msg)
        return False


def scheduled_worker_job():
    """Background job executed automatically every 3 hours."""
    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] Running 3-Hour Scheduled Post Worker...")
    next_post = db.get_next_pending_post()
    if not next_post:
        print("[Worker] No pending posts in queue. Skipping.")
        return
        
    process_single_post(next_post)


# Setup APScheduler
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(
    func=scheduled_worker_job,
    trigger="interval",
    hours=POSTING_INTERVAL_HOURS,
    id="auto_instagram_poster",
    name="3-Hour Instagram Poster"
)
scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))


@app.route("/")
def index():
    login_info = instagram_bot.check_login_status()
    posts = db.get_all_posts()
    next_post = db.get_next_pending_post()
    return render_template(
        "dashboard.html",
        login_info=login_info,
        posts=posts,
        next_post=next_post,
        interval_hours=POSTING_INTERVAL_HOURS
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_type = request.form.get("login_type", "password")

        # 1. Cookie-based Login (Instant & Highly Reliable)
        if login_type == "cookie":
            cookie_data = request.form.get("cookie_data", "").strip()
            if not cookie_data:
                flash("অনুগ্রহ করে আপনার Instagram sessionid বা Cookie পেস্ট করুন।", "danger")
                return render_template("login.html", active_tab="cookie")
                
            result = instagram_bot.login_instagram_by_cookie(cookie_data)
            if result.get("success"):
                flash(result.get("message", "কুকিজ দিয়ে সফলভাবে লগইন হয়েছে!"), "success")
                return redirect(url_for("index"))
            else:
                flash(result.get("message", "Cookie লগইন ব্যর্থ হয়েছে।"), "danger")
                return render_template("login.html", active_tab="cookie")

        # 2. Username & Password Login
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        code = request.form.get("verification_code", "").strip()
        two_factor_identifier = request.form.get("two_factor_identifier", "").strip()
        
        if not username or (not password and not code):
            flash("Username এবং password দুটোই দেওয়া আবশ্যক।", "danger")
            return render_template("login.html", username=username, active_tab="password")
            
        result = instagram_bot.login_instagram(
            username=username,
            password=password,
            code=code if code else None,
            two_factor_identifier=two_factor_identifier if two_factor_identifier else None
        )
        
        if result.get("success"):
            flash(result.get("message", "Login successful!"), "success")
            return redirect(url_for("index"))
            
        elif result.get("needs_2fa"):
            flash("Instagram একটি 2FA / Verification কোড পাঠিয়েছে। নিচে কোডটি লিখুন।", "warning")
            return render_template(
                "login.html",
                username=username,
                password=password,
                needs_2fa=True,
                active_tab="password",
                two_factor_identifier=result.get("two_factor_identifier")
            )
        else:
            flash(result.get("message", "Login failed. Check details."), "danger")
            return render_template("login.html", username=username, active_tab="password")
            
    return render_template("login.html", active_tab="cookie")


@app.route("/logout", methods=["POST", "GET"])
def logout():
    instagram_bot.logout_instagram()
    flash("Logged out successfully from Instagram.", "info")
    return redirect(url_for("index"))


@app.route("/add-post", methods=["POST"])
def add_new_post():
    drive_url = request.form.get("drive_url", "").strip()
    title = request.form.get("title", "").strip()
    caption = request.form.get("caption", "").strip()
    hashtags = request.form.get("hashtags", "").strip()
    
    if not drive_url:
        flash("Google Drive URL is required!", "danger")
        return redirect(url_for("index"))
        
    drive_id = drive_handler.extract_drive_id(drive_url)
    if not drive_id:
        flash("Invalid Google Drive link. Please make sure the link is public (Anyone with the link).", "danger")
        return redirect(url_for("index"))
        
    # Auto-format hashtags if user forgot '#'
    if hashtags:
        tags = [t if t.startswith('#') else f"#{t}" for t in hashtags.split()]
        hashtags = " ".join(tags)
        
    db.add_post(drive_url=drive_url, title=title, caption=caption, hashtags=hashtags)
    flash("Post added to the queue! It will be posted according to schedule.", "success")
    return redirect(url_for("index"))


@app.route("/post-now/<int:post_id>", methods=["POST"])
def post_now(post_id):
    """Trigger manual post execution immediately without waiting 3 hours."""
    post = db.get_post_by_id(post_id)
    if not post:
        flash("Post not found.", "danger")
        return redirect(url_for("index"))
        
    success = process_single_post(post)
    if success:
        flash(f"Post #{post_id} was successfully published to Instagram!", "success")
    else:
        post_updated = db.get_post_by_id(post_id)
        flash(f"Failed to publish Post #{post_id}: {post_updated.get('error_message')}", "danger")
        
    return redirect(url_for("index"))


@app.route("/delete-post/<int:post_id>", methods=["POST"])
def delete_post_route(post_id):
    db.delete_post(post_id)
    flash(f"Post #{post_id} removed from queue.", "info")
    return redirect(url_for("index"))


@app.route("/health")
@app.route("/ping")
def health():
    """
    Keep-alive endpoint for UptimeRobot.
    UptimeRobot should ping this URL every 5 minutes so Render never sleeps.
    """
    return jsonify({
        "status": "online",
        "service": "Instagram Auto Poster",
        "time_utc": datetime.utcnow().isoformat(),
        "login_status": instagram_bot.check_login_status().get("logged_in")
    })


@app.route("/api/cron", methods=["GET", "POST"])
def manual_cron():
    """External cron trigger endpoint if user wants to trigger posting via cron-job.org."""
    next_post = db.get_next_pending_post()
    if not next_post:
        return jsonify({"status": "empty", "message": "No pending posts in queue"})
    
    success = process_single_post(next_post)
    return jsonify({
        "status": "success" if success else "failed",
        "post_id": next_post['id']
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
