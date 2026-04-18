# SVG icon paths
ICON_PATHS = {
    "home": "M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z",
    "search": "M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z",
    "artist": {
        "viewBox": "0 0 24 24",
        "body": """
            <path d="M12 12.2a3.3 3.3 0 1 0 0-6.6 3.3 3.3 0 0 0 0 6.6Z" fill="none" stroke="{color}" stroke-width="1.8"/>
            <path d="M5.8 18.2a6.55 6.55 0 0 1 12.4 0" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
            <path d="M19.25 6.15c.95.72 1.55 1.86 1.55 3.15 0 1.3-.6 2.44-1.55 3.16M4.75 6.15C3.8 6.87 3.2 8 3.2 9.3c0 1.3.6 2.44 1.55 3.16" fill="none" stroke="{color}" stroke-width="1.55" stroke-linecap="round"/>
        """,
    },
    "add": "M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z",
    "heart_on": "M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z",
    "heart_off": "M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35zm0-2.7l1.45-1.32C17.6 13.64 20 11.22 20 8.5c0-2.1-1.6-3.8-3.7-3.8-1.74 0-2.78.88-3.66 1.76l-.64.66-.64-.66C10.48 5.58 9.44 4.7 7.7 4.7 5.6 4.7 4 6.4 4 8.5c0 2.72 2.4 5.14 6.55 8.82L12 18.65z",
    "play": "M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 0 1 0 1.971l-11.54 6.347a1.125 1.125 0 0 1-1.667-.985V5.653Z",
    "pause": "M6 19h4V5H6v14zm8-14v14h4V5h-4z",
    "skip_next": "M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z",
    "skip_prev": "M6 6h2v12H6zm3.5 6l8.5 6V6z",
    "shuffle": "M10.59 9.17L5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 5.41 14.5 4zm.33 9.41l-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z",
    "repeat": "M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z",
    "repeat_one": "M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4zm-4-2V9h-1l-2 1v1h1.5v4H13z",
    "queue": {
        "viewBox": "0 0 24 24",
        "body": """
            <path d="M9 6.5h10M9 12h10M9 17.5h7" fill="none" stroke="{color}" stroke-width="1.9" stroke-linecap="round"/>
            <circle cx="4.5" cy="6.5" r="1.05" fill="{color}"/>
            <circle cx="4.5" cy="12" r="1.05" fill="{color}"/>
            <circle cx="4.5" cy="17.5" r="1.05" fill="{color}"/>
        """,
    },
    "mic": {
        "viewBox": "0 0 24 24",
        "body": """
            <path d="M12 14.7a3.65 3.65 0 0 0 3.65-3.65v-3.2a3.65 3.65 0 1 0-7.3 0v3.2A3.65 3.65 0 0 0 12 14.7Z" fill="none" stroke="{color}" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M10.15 7.85h3.7M10.35 9.9h3.3" fill="none" stroke="{color}" stroke-width="1.55" stroke-linecap="round"/>
            <path d="M6.9 11.25a5.1 5.1 0 0 0 10.2 0" fill="none" stroke="{color}" stroke-width="1.85" stroke-linecap="round"/>
            <path d="M12 15.95v2.6M9.25 19.35h5.5" fill="none" stroke="{color}" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round"/>
        """,
    },
    "download": {
        "viewBox": "0 0 24 24",
        "body": """
            <path d="M12 4.5v9m0 0 3.6-3.6M12 13.5 8.4 9.9M5 18.5h14" fill="none" stroke="{color}" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>
        """,
    },
    "download_done": {
        "viewBox": "0 0 24 24",
        "body": """
            <circle cx="12" cy="12" r="8.5" fill="none" stroke="{color}" stroke-width="1.75"/>
            <path d="m8.6 12.2 2.2 2.2 4.8-5" fill="none" stroke="{color}" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>
        """,
    },
    "folder": "M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z",
    "eq": "M10 20h4V4h-4v16zm-6 0h4v-8H4v8zM16 9v11h4V9h-4z",
    "lyrics": {
        "viewBox": "0 0 24 24",
        "body": """
            <path d="M5.5 6.5h13M5.5 10.5h13M5.5 14.5h8M5.5 18.5h10" fill="none" stroke="{color}" stroke-width="1.85" stroke-linecap="round"/>
        """,
    },
    "miniplayer": "M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z",
    "mix": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z",
    "arrow_back": "M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z",
    "share": "M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z",
    "copy": "M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z",
    "timer": "M15 1H9v2h6V1zm-4 13h2V8h-2v6zm8.03-6.61l1.42-1.42c-.43-.51-.9-.99-1.41-1.41l-1.42 1.42C16.07 4.74 14.12 4 12 4c-4.97 0-9 4.03-9 9s4.02 9 9 9 9-4.03 9-9c0-2.12-.74-4.07-1.97-5.61zM12 20c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z",
    "stats": "M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z",
    "palette": "M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9c.83 0 1.5-.67 1.5-1.5 0-.39-.15-.74-.39-1.01-.23-.26-.38-.61-.38-.99 0-.83.67-1.5 1.5-1.5H16c2.76 0 5-2.24 5-5 0-4.42-4.03-8-9-8zm-5.5 9c-.83 0-1.5-.67-1.5-1.5S5.67 9 6.5 9 8 9.67 8 10.5 7.33 12 6.5 12zm3-4C8.67 8 8 7.33 8 6.5S8.67 5 9.5 5s1.5.67 1.5 1.5S10.33 8 9.5 8zm5 0c-.83 0-1.5-.67-1.5-1.5S13.67 5 14.5 5s1.5.67 1.5 1.5S15.33 8 14.5 8zm3 4c-.83 0-1.5-.67-1.5-1.5S16.67 9 17.5 9s1.5.67 1.5 1.5-.67 1.5-1.5 1.5z",
    "wifi_off": "M24 .01c0-.01 0-.01 0 0L0 0l9.28 9.28C6.01 10.06 3.07 11.59 .64 13.76l2.39 2.39C4.99 14.22 7.92 12.93 11.1 12.4l2.68 2.68c-1.46.35-2.82 1-3.99 1.92l3.21 3.21 1 1 1-1 3.21-3.21c-1.17-.92-2.53-1.57-3.99-1.92l2.68-2.68c3.18.52 6.11 1.81 8.07 3.75l2.39-2.39C24.93 11.59 21.99 10.06 18.72 9.28L24 4.01v-.01z",
    "settings": {
        "viewBox": "0 0 24 24",
        "body": """
            <path d="M12 8.1a3.9 3.9 0 1 0 0 7.8 3.9 3.9 0 0 0 0-7.8Z" fill="none" stroke="{color}" stroke-width="1.8"/>
            <path d="M19.1 13.25c.05-.4.08-.82.08-1.25 0-.43-.03-.85-.08-1.25l2.02-1.58-1.9-3.3-2.41.95a7.54 7.54 0 0 0-2.16-1.25l-.37-2.56h-3.8l-.37 2.56c-.78.28-1.5.7-2.17 1.25l-2.4-.95-1.9 3.3 2.02 1.58A9.7 9.7 0 0 0 4.8 12c0 .43.03.85.08 1.25L2.86 14.83l1.9 3.3 2.4-.95c.67.55 1.4.97 2.17 1.25l.37 2.56h3.8l.37-2.56c.77-.28 1.49-.7 2.16-1.25l2.41.95 1.9-3.3-2.02-1.58Z" fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round"/>
        """,
    },
    "volume": "M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z",
    "close": "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z",
    "minus": "M19 13H5v-2h14v2z",
    "music": {
        "viewBox": "0 0 24 24",
        "body": """
            <path d="M10 17.5a2.5 2.5 0 1 1-2.5-2.5A2.5 2.5 0 0 1 10 17.5Zm0 0V7.5l8-1.8v8.3" fill="none" stroke="{color}" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M18 14.8a2.5 2.5 0 1 1-2.5-2.5 2.5 2.5 0 0 1 2.5 2.5Z" fill="none" stroke="{color}" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round"/>
        """,
    },
    "radio": {
        "viewBox": "0 0 24 24",
        "body": """
            <path d="m7 5 10 4M5.5 9h13a2.5 2.5 0 0 1 2.5 2.5v5A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5v-5A2.5 2.5 0 0 1 5.5 9Z" fill="none" stroke="{color}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="9" cy="14" r="2.2" fill="none" stroke="{color}" stroke-width="1.75"/>
            <path d="M15 13h3M15 16h2" fill="none" stroke="{color}" stroke-width="1.75" stroke-linecap="round"/>
        """,
    },
    "link": "M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z",
    "delete": "M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z",
    "playlist_add": "M2 14h2v-2H2v2zm0 4h2v-2H2v2zm0-8h2V8H2v2zm4 4h12v-2H6v2zm0 4h12v-2H6v2zM6 8v2h12V8H6zm10 1v2h2v2h2v-2h2v-2h-2V7h-2v2h-2z",
    "headphone": {
        "viewBox": "0 0 24 24",
        "body": """
            <path d="M12 3a9 9 0 0 0-9 9v3a3 3 0 0 0 3 3h1a1 1 0 0 0 1-1v-4a1 1 0 0 0-1-1H5.07A7 7 0 0 1 19 12h-2a1 1 0 0 0-1 1v4a1 1 0 0 0 1 1h1a3 3 0 0 0 3-3v-3a9 9 0 0 0-9-9Z" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        """,
    },
    "speed": {
        "viewBox": "0 0 24 24",
        "body": """
            <path d="M12 3a9 9 0 1 1-6.36 2.64" fill="none" stroke="{color}" stroke-width="1.85" stroke-linecap="round"/>
            <path d="m12 12 3.5-5" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
            <circle cx="12" cy="12" r="1.4" fill="{color}"/>
            <path d="M8 3.5h3M13 3.5h3" fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round"/>
        """,
    },
}
