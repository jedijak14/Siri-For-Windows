package local.siriforwindows.assistant;

import android.app.Activity;
import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.webkit.WebChromeClient;
import android.webkit.ValueCallback;
import android.webkit.PermissionRequest;
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
    private ValueCallback<Uri[]> pendingFiles;
    private PermissionRequest pendingCamera;
    private String trustedOrigin="";
    private static final int FILE_PICKER=101, CAMERA_PERMISSION=102;
    private String origin(Uri uri){return uri.getScheme()+"://"+uri.getHost()+":"+(uri.getPort()==-1?443:uri.getPort());}
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
        TextView note=new TextView(this);note.setText("Only connect to a server you own. That server can access content you explicitly submit. Image/file picking and camera photos are supported after permission. Screen sharing and Windows app controls are not supported on Android.");note.setTextColor(Color.GRAY);note.setPadding(0,20,0,0);layout.addView(note);
        setContentView(layout);
        connect.setOnClickListener(v->{String address=url.getText().toString().trim();Uri uri=Uri.parse(address);if(!"https".equals(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null){url.setError("Enter a valid HTTPS server address");return;}
            new AlertDialog.Builder(this).setTitle("Trust this server?").setMessage("Only continue if you control "+uri.getHost()+". This server receives the prompts and files you submit.").setNegativeButton("Cancel",null).setPositiveButton("Connect",(d,w)->{prefs.edit().putString("server",address).apply();open(address,uri.getHost());}).show();});
    }
    private void open(String address,String host){
        trustedOrigin=origin(Uri.parse(address));
        web=new WebView(this);web.setBackgroundColor(Color.rgb(12,13,17));web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);web.getSettings().setAllowFileAccess(false);web.getSettings().setAllowContentAccess(false);web.getSettings().setMixedContentMode(android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.setWebViewClient(new WebViewClient(){@Override public boolean shouldOverrideUrlLoading(WebView v,android.webkit.WebResourceRequest req){Uri u=req.getUrl();return !"https".equals(u.getScheme())||!trustedOrigin.equals(origin(u));}});
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(pendingFiles!=null)pendingFiles.onReceiveValue(null);
                pendingFiles=callback;
                Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT);picker.addCategory(Intent.CATEGORY_OPENABLE);picker.setType("*/*");
                picker.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"image/png","image/jpeg","image/webp","text/plain","text/markdown","text/csv","application/json","message/rfc822","text/calendar","text/html"});
                picker.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==FileChooserParams.MODE_OPEN_MULTIPLE);picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                try{startActivityForResult(picker,FILE_PICKER);}catch(Exception error){pendingFiles.onReceiveValue(null);pendingFiles=null;}
                return true;
            }
            @Override public void onPermissionRequest(PermissionRequest request){
                runOnUiThread(()->{
                    if(!trustedOrigin.equals(origin(request.getOrigin()))||request.getResources().length!=1||!PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(request.getResources()[0])){request.deny();return;}
                    if(pendingCamera!=null)pendingCamera.deny();pendingCamera=request;
                    if(checkSelfPermission(Manifest.permission.CAMERA)==PackageManager.PERMISSION_GRANTED){request.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});pendingCamera=null;}
                    else requestPermissions(new String[]{Manifest.permission.CAMERA},CAMERA_PERMISSION);
                });
            }
            @Override public void onPermissionRequestCanceled(PermissionRequest request){if(pendingCamera==request)pendingCamera=null;}
        });
        setContentView(web);web.loadUrl(address);
    }
    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode==FILE_PICKER&&pendingFiles!=null){
            Uri[] files=null;
            if(resultCode==RESULT_OK&&data!=null){
                java.util.ArrayList<Uri> values=new java.util.ArrayList<>();
                if(data.getClipData()!=null){for(int i=0;i<Math.min(3,data.getClipData().getItemCount());i++)values.add(data.getClipData().getItemAt(i).getUri());}
                else if(data.getData()!=null)values.add(data.getData());
                values.removeIf(uri->!"content".equals(uri.getScheme()));files=values.toArray(new Uri[0]);
            }
            pendingFiles.onReceiveValue(files);pendingFiles=null;
        }
    }
    @Override public void onRequestPermissionsResult(int requestCode,String[] permissions,int[] results){
        super.onRequestPermissionsResult(requestCode,permissions,results);
        if(requestCode==CAMERA_PERMISSION&&pendingCamera!=null){
            if(results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED&&web!=null&&trustedOrigin.equals(origin(pendingCamera.getOrigin())))pendingCamera.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
            else pendingCamera.deny();pendingCamera=null;
        }
    }
    @Override public void onBackPressed(){if(web!=null){web.destroy();web=null;recreate();}else super.onBackPressed();}
    @Override protected void onDestroy(){if(pendingFiles!=null){pendingFiles.onReceiveValue(null);pendingFiles=null;}if(pendingCamera!=null){pendingCamera.deny();pendingCamera=null;}if(web!=null)web.destroy();super.onDestroy();}
}
