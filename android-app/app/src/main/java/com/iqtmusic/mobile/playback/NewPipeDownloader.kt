package com.iqtmusic.mobile.playback

import org.schabi.newpipe.extractor.downloader.Downloader
import org.schabi.newpipe.extractor.downloader.Request
import org.schabi.newpipe.extractor.downloader.Response
import java.net.HttpURLConnection
import java.net.URL

/**
 * NewPipeExtractor için HTTP downloader implementasyonu.
 * YouTube stream URL'lerini çihazın kendi IP'sinden çeker.
 */
object NewPipeDownloader : Downloader() {

    private const val USER_AGENT =
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    override fun execute(request: Request): Response {
        val conn = URL(request.url()).openConnection() as HttpURLConnection
        conn.connectTimeout = 15_000
        conn.readTimeout = 20_000
        conn.setRequestProperty("User-Agent", USER_AGENT)

        request.headers().forEach { (key, values) ->
            values.forEach { value -> conn.addRequestProperty(key, value) }
        }

        if (request.httpMethod() == "POST") {
            conn.requestMethod = "POST"
            conn.doOutput = true
            request.dataToSend()?.let { conn.outputStream.write(it) }
        }

        val responseCode = conn.responseCode
        val responseBody = runCatching {
            conn.inputStream.bufferedReader().readText()
        }.getOrElse {
            conn.errorStream?.bufferedReader()?.readText() ?: ""
        }

        val headers = conn.headerFields
            .filterKeys { it != null }
            .mapValues { (_, v) -> v }

        conn.disconnect()

        return Response(responseCode, conn.responseMessage, headers, responseBody, request.url())
    }
}
