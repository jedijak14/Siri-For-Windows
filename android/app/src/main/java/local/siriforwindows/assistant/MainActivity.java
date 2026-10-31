package local.siriforwindows.assistant;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.view.View;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.*;

/** Explicit HTTPS companion connection. No JS bridge or background collection. */
public class MainActivity extends Activity {
    private WebView web;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        SharedPreferences prefs=getSharedPreferences("siri",MODE_PRIVATE);
        LinearLayout layout=new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(36,50,36,30); layout.setBackgroundColor(Color.rgb(15,15,22));
        ImageView logo=new ImageView(this);logo.setImageResource(local.siriforwindows.assistant.R.drawable.siri_logo);LinearLayout.LayoutParams logoSize=new LinearLayout.LayoutParams(130,130);logoSize.bottomMargin=30;layout.addView(logo,logoSize);
        TextView title=new TextView(this);title.setText("Siri\nfor Windows · Android companion");title.setTextSize(30);title.setTextColor(Color.rgb(232,226,216));layout.addView(title);
        TextView intro=new TextView(this);intro.setText("What can I help you with?\n\nConnect to your own HTTPS Siri companion server. Your phone cannot reach your PC through localhost. This app does not connect to Apple services.\n");intro.setTextSize(15);intro.setTextColor(Color.LTGRAY);intro.setPadding(0,30,0,20);layout.addView(intro);
        EditText url=new EditText(this);url.setSingleLine(true);url.setTextColor(Color.WHITE);url.setHintTextColor(Color.GRAY);url.setHint("https://your-trusted-siri-server");url.setText(prefs.getString("server",""));layout.addView(url);
        Button connect=new Button(this);connect.setText("Connect to my server ↗");layout.addView(connect);
        TextView note=new TextView(this);note.setText("Only connect to a server you own. That server can access content you explicitly submit. Camera capture, screen sharing, and Windows app controls are not supported in this Android wrapper.");note.setTextColor(Color.GRAY);note.setPadding(0,20,0,0);layout.addView(note);
        setContentView(layout);
        connect.setOnClickListener(v->{String address=url.getText().toString().trim();Uri uri=Uri.parse(address);if(!"https".equals(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null){url.setError("Enter a valid HTTPS server address");return;}
            new AlertDialog.Builder(this).setTitle("Trust this server?").setMessage("Only continue if you control "+uri.getHost()+". This server receives the prompts and files you submit.").setNegativeButton("Cancel",null).setPositiveButton("Connect",(d,w)->{prefs.edit().putString("server",address).apply();open(address,uri.getHost());}).show();});
    }
    private void open(String address,String host){
        web=new WebView(this);web.setBackgroundColor(Color.rgb(12,13,17));web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);web.getSettings().setAllowFileAccess(false);web.getSettings().setAllowContentAccess(false);web.getSettings().setMixedContentMode(android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.setWebViewClient(new WebViewClient(){@Override public boolean shouldOverrideUrlLoading(WebView v,android.webkit.WebResourceRequest req){Uri u=req.getUrl();return !"https".equals(u.getScheme())||!host.equals(u.getHost());}});
        setContentView(web);web.loadUrl(address);
    }
    @Override public void onBackPressed(){if(web!=null){web.destroy();web=null;recreate();}else super.onBackPressed();}
    @Override protected void onDestroy(){if(web!=null)web.destroy();super.onDestroy();}
}
