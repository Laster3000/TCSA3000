// TCSA3000 - icono de bandeja y menu. Sin ventana de consola (winexe). Portatil: usa la carpeta donde esta el .exe.
// Compilar: bandeja\compilar.cmd  (csc de .NET Framework 4, incluido en Windows)
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Net;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("TCSA3000")]
[assembly: System.Reflection.AssemblyProduct("TCSA3000")]
[assembly: System.Reflection.AssemblyVersion("0.4.0.4")]

static class Programa
{
    [STAThread]
    static void Main(string[] args)
    {
        bool nuevo;
        using (var mutex = new Mutex(true, "Local\\TCSA3000-Bandeja", out nuevo))
        {
            if (!nuevo)
            {
                // Ya hay un icono: abrir el centro de control en lugar de duplicar.
                Bandeja.LanzarCli(Bandeja.Home(), "panel", false);
                return;
            }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new Bandeja());
        }
    }
}

class Bandeja : ApplicationContext
{
    readonly NotifyIcon icono = new NotifyIcon();
    readonly ContextMenuStrip menu = new ContextMenuStrip();
    readonly System.Windows.Forms.Timer reloj = new System.Windows.Forms.Timer();
    readonly string home = Home();
    readonly Icon icOn, icOff;
    ToolStripMenuItem cabecera, proyectos, arrancar, parar, reiniciar;
    bool? enMarcha = null;
    string version = "", ubicacion = "";
    volatile bool comprobando = false;

    public static void Log(string texto)
    {
        try
        {
            var f = Path.Combine(Home(), "data", "bandeja.log");
            Directory.CreateDirectory(Path.GetDirectoryName(f));
            if (File.Exists(f) && new FileInfo(f).Length > 200000) File.Delete(f);
            File.AppendAllText(f, DateTime.Now.ToString("s") + " " + texto + Environment.NewLine);
        }
        catch { }
    }

    public static string Home()
    {
        return AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
    }

    public Bandeja()
    {
        icOn = Dibujar(Color.FromArgb(15, 118, 110), Color.FromArgb(34, 197, 94));
        icOff = Dibujar(Color.FromArgb(90, 98, 112), Color.FromArgb(220, 38, 38));
        ConstruirMenu();
        var asegurarHandle = menu.Handle;  // necesario para BeginInvoke antes de abrir el menu por primera vez
        icono.Icon = icOff;
        icono.Text = "TCSA3000 - comprobando...";
        icono.ContextMenuStrip = menu;
        icono.Visible = true;
        icono.MouseDoubleClick += delegate { Panel(""); };
        icono.MouseClick += delegate(object s, MouseEventArgs e) { if (e.Button == MouseButtons.Left) Panel(""); };
        reloj.Interval = 5000;
        reloj.Tick += delegate { Comprobar(false); };
        reloj.Start();
        Comprobar(true);
    }

    // ------------------------------------------------------------------ menu
    ToolStripMenuItem Item(string texto, EventHandler accion)
    {
        var i = new ToolStripMenuItem(texto);
        if (accion != null) i.Click += accion;
        return i;
    }

    void ConstruirMenu()
    {
        menu.ShowImageMargin = false;
        menu.Font = new Font("Segoe UI", 9.5f);
        cabecera = new ToolStripMenuItem("TCSA3000") { Enabled = false };
        cabecera.Font = new Font("Segoe UI", 9.5f, FontStyle.Bold);
        var abrir = Item("Abrir centro de control", delegate { Panel(""); });
        abrir.Font = new Font("Segoe UI", 9.5f, FontStyle.Bold);
        proyectos = Item("Proyectos", null);
        proyectos.DropDownItems.Add(new ToolStripMenuItem("(cargando...)") { Enabled = false });

        var servicio = Item("Servicio", null);
        arrancar = Item("Arrancar", delegate { Accion("arrancar", "Arrancando TCSA3000..."); });
        parar = Item("Parar", delegate { Accion("parar", "Parando TCSA3000 (las IAs quedan en solo lectura)..."); });
        reiniciar = Item("Reiniciar", delegate { Accion("reiniciar", "Reiniciando TCSA3000..."); });
        servicio.DropDownItems.AddRange(new ToolStripItem[] { arrancar, parar, reiniciar });

        var ajustes = Item("Configuracion", null);
        ajustes.DropDownItems.AddRange(new ToolStripItem[] {
            Item("Conectar una IA (MCP)...", delegate { Panel("ia"); }),
            Item("ChatGPT por tunel seguro...", delegate { Panel("ia"); }),
            Item("Normas y directrices...", delegate { Panel("normas"); }),
            Item("Credenciales...", delegate { Panel("cred"); }),
            Item("Ubicacion y ajustes...", delegate { Panel("ajustes"); }),
            Item("Ver donde se ejecuta", delegate { Aviso("TCSA3000 se ejecuta en", home + (version.Length > 0 ? "\nVersion " + version : ""), ToolTipIcon.Info); }),
            Item("Abrir carpeta de TCSA3000", delegate { Process.Start("explorer.exe", "\"" + home + "\""); })
        });

        menu.Items.AddRange(new ToolStripItem[] {
            cabecera, new ToolStripSeparator(),
            abrir, proyectos,
            Item("LISTA", delegate { Panel("lista"); }),
            Item("Descubrimientos", delegate { Panel("desc"); }),
            new ToolStripSeparator(),
            Item("Copiar a Drive ahora (respaldo)", delegate { Accion("respaldo", "Copiando la continuidad a Drive..."); }),
            servicio, ajustes,
            new ToolStripSeparator(),
            Item("Salir y detener TCSA3000", delegate { Salir(true); }),
            Item("Quitar solo el icono (el servicio sigue)", delegate { Salir(false); })
        });
        menu.Opening += delegate { CargarProyectos(); };
    }

    void CargarProyectos()
    {
        proyectos.DropDownItems.Clear();
        try
        {
            var root = LeerConfig("tcsaRoot", "TCSA");
            if (!Path.IsPathRooted(root)) root = Path.Combine(home, root);
            var cat = Path.Combine(root, "02-CATALOGO", "PROYECTOS.json");
            var json = new JavaScriptSerializer().DeserializeObject(File.ReadAllText(cat)) as Dictionary<string, object>;
            var lista = json != null && json.ContainsKey("projects") ? json["projects"] as object[] : null;
            if (lista != null)
                foreach (var o in lista)
                {
                    var p = o as Dictionary<string, object>;
                    if (p == null || !p.ContainsKey("projectId")) continue;
                    string id = Convert.ToString(p["projectId"]);
                    string nombre = p.ContainsKey("name") ? Convert.ToString(p["name"]) : id;
                    string estado = p.ContainsKey("status") ? Convert.ToString(p["status"]) : "";
                    var it = Item(nombre + "   (" + id + ")", delegate { Panel("proyectos/" + Uri.EscapeDataString(id)); });
                    it.ToolTipText = estado;
                    proyectos.DropDownItems.Add(it);
                }
        }
        catch (Exception ex)
        {
            proyectos.DropDownItems.Add(new ToolStripMenuItem("No se pudo leer el catalogo: " + ex.Message) { Enabled = false });
        }
        proyectos.DropDownItems.Add(new ToolStripSeparator());
        proyectos.DropDownItems.Add(Item("Nuevo proyecto...", delegate { Panel("proyectos"); }));
    }

    // ------------------------------------------------------------------ acciones
    void Panel(string seccion)
    {
        if (enMarcha != true) Aviso("TCSA3000", "Arrancando el servicio y abriendo el centro de control...", ToolTipIcon.Info);
        LanzarCli(home, "panel" + (seccion.Length > 0 ? " " + seccion : ""), false);
    }

    void Accion(string orden, string mensaje)
    {
        Aviso("TCSA3000", mensaje, ToolTipIcon.Info);
        ThreadPool.QueueUserWorkItem(delegate
        {
            string salida = LanzarCli(home, orden, true);
            Log(orden + " -> " + (salida ?? "(sin salida)").Replace("\r", " ").Replace("\n", " "));
            var m = Regex.Match(salida ?? "", "\"(servicio|estado)\":\\s*\"([^\"]+)\"");
            string res = m.Success ? m.Groups[2].Value.Replace('_', ' ').ToLower() : "hecho";
            bool mal = res.Contains("no ") || res.Contains("bloque") || res.Contains("error");
            menu.BeginInvoke((MethodInvoker)delegate
            {
                Aviso("TCSA3000", char.ToUpper(res[0]) + res.Substring(1), mal ? ToolTipIcon.Warning : ToolTipIcon.Info);
                Comprobar(true);
            });
        });
    }

    void Salir(bool detener)
    {
        reloj.Stop();
        if (detener) LanzarCli(home, "parar", true);
        icono.Visible = false;
        icono.Dispose();
        ExitThread();
    }

    void Aviso(string titulo, string texto, ToolTipIcon tipo)
    {
        icono.BalloonTipTitle = titulo;
        icono.BalloonTipText = texto;
        icono.BalloonTipIcon = tipo;
        icono.ShowBalloonTip(3500);
    }

    // ------------------------------------------------------------------ estado del servicio
    void Comprobar(bool arrancarSiParado)
    {
        if (comprobando) return;
        comprobando = true;
        int puerto = Puerto();
        ThreadPool.QueueUserWorkItem(delegate
        {
            string cuerpo = null;
            try
            {
                var req = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:" + puerto + "/health");
                req.Timeout = 1500; req.Proxy = null;
                using (var r = req.GetResponse())
                using (var sr = new StreamReader(r.GetResponseStream())) cuerpo = sr.ReadToEnd();
            }
            catch { }
            bool ok = cuerpo != null && cuerpo.Contains("\"OK\"");
            if (ok)
            {
                var v = Regex.Match(cuerpo, "\"version\":\\s*\"([^\"]+)\""); if (v.Success) version = v.Groups[1].Value;
                var u = Regex.Match(cuerpo, "\"ubicacion\":\\s*\"((?:[^\"\\\\]|\\\\.)*)\""); if (u.Success) ubicacion = Regex.Unescape(u.Groups[1].Value);
            }
            try
            {
                menu.BeginInvoke((MethodInvoker)delegate
                {
                    Pintar(ok);
                    if (!ok && arrancarSiParado) Accion("arrancar", "Arrancando TCSA3000...");
                });
            }
            catch (Exception ex) { Log("Comprobar: " + ex.Message); }
            comprobando = false;
        });
    }

    void Pintar(bool ok)
    {
        if (enMarcha == ok) return;
        bool habiaEstado = enMarcha.HasValue;
        enMarcha = ok;
        icono.Icon = ok ? icOn : icOff;
        string t = ok ? "TCSA3000 en marcha" + (version.Length > 0 ? " - v" + version : "") : "TCSA3000 parado";
        icono.Text = t.Length > 63 ? t.Substring(0, 63) : t;
        cabecera.Text = ok ? "TCSA3000  -  en marcha" : "TCSA3000  -  parado";
        cabecera.ForeColor = ok ? Color.FromArgb(21, 128, 61) : Color.FromArgb(185, 28, 28);
        arrancar.Enabled = !ok; parar.Enabled = ok; reiniciar.Enabled = ok;
        if (habiaEstado && !ok) Aviso("TCSA3000 se ha detenido", "Las IAs siguen pudiendo leer (modo degradado). Usa Servicio > Arrancar.", ToolTipIcon.Warning);
    }

    // ------------------------------------------------------------------ utilidades
    string LeerConfig(string clave, string porDefecto)
    {
        try
        {
            var f = Path.Combine(home, "tcsa3000.config.json");
            if (!File.Exists(f)) return porDefecto;
            var d = new JavaScriptSerializer().DeserializeObject(File.ReadAllText(f)) as Dictionary<string, object>;
            return d != null && d.ContainsKey(clave) && d[clave] != null ? Convert.ToString(d[clave]) : porDefecto;
        }
        catch { return porDefecto; }
    }

    int Puerto()
    {
        int p;
        return int.TryParse(LeerConfig("port", "18730"), out p) ? p : 18730;
    }

    public static string LanzarCli(string home, string orden, bool esperar)
    {
        string py = Path.Combine(home, "runtime", "pythonw.exe");
        if (!File.Exists(py)) py = "pythonw.exe";
        var psi = new ProcessStartInfo(py, "-B \"" + Path.Combine(home, "tcsa3000", "cli.py") + "\" " + orden)
        {
            UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = home,
            RedirectStandardOutput = esperar, RedirectStandardError = esperar
        };
        psi.EnvironmentVariables["TCSA3000_HOME"] = home;
        psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        try
        {
            using (var p = Process.Start(psi))
            {
                if (!esperar) return null;
                string o = p.StandardOutput.ReadToEnd();
                p.WaitForExit(60000);
                return o;
            }
        }
        catch (Exception ex)
        {
            Log("LanzarCli " + orden + ": " + ex.Message);
            return "{\"estado\": \"ERROR " + ex.Message.Replace("\"", "'") + "\"}";
        }
    }

    static Icon Dibujar(Color fondo, Color punto)
    {
        var bmp = new Bitmap(32, 32);
        using (var g = Graphics.FromImage(bmp))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAliasGridFit;
            using (var path = new GraphicsPath())
            {
                int r = 8;
                path.AddArc(1, 1, r * 2, r * 2, 180, 90); path.AddArc(30 - r * 2, 1, r * 2, r * 2, 270, 90);
                path.AddArc(30 - r * 2, 30 - r * 2, r * 2, r * 2, 0, 90); path.AddArc(1, 30 - r * 2, r * 2, r * 2, 90, 90);
                path.CloseFigure();
                using (var b = new SolidBrush(fondo)) g.FillPath(b, path);
            }
            using (var f = new Font("Segoe UI", 15f, FontStyle.Bold, GraphicsUnit.Pixel))
            using (var sf = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center })
                g.DrawString("T", f, Brushes.White, new RectangleF(0, 0, 27, 31), sf);
            using (var b = new SolidBrush(punto)) g.FillEllipse(b, 19, 19, 12, 12);
            using (var pen = new Pen(Color.White, 2f)) g.DrawEllipse(pen, 19, 19, 12, 12);
        }
        return Icon.FromHandle(bmp.GetHicon());
    }
}
