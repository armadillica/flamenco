var argv         = require('minimist')(process.argv.slice(2));
var autoprefixer = require('gulp-autoprefixer');
var cache        = require('gulp-cached');
var chmod        = require('gulp-chmod');
var concat       = require('gulp-concat');
var git          = require('gulp-git');
var gulp         = require('gulp');
var gulpif       = require('gulp-if');
var livereload   = require('gulp-livereload');
var plumber      = require('gulp-plumber');
var pug          = require('gulp-pug');
var rename       = require('gulp-rename');
var sass         = require('gulp-sass');
var sourcemaps   = require('gulp-sourcemaps');
var uglify       = require('gulp-uglify-es').default;
var browserify   = require('browserify');
var babelify     = require('babelify');
var sourceStream = require('vinyl-source-stream');
var glob         = require('glob');
var es           = require('event-stream');
var path         = require('path');
var buffer 		 = require('vinyl-buffer');

var enabled = {
    chmod: argv.production,
    cleanup: argv.production,
    failCheck: argv.production,
    liveReload: !argv.production,
    maps: argv.production,
    prettyPug: !argv.production,
    uglify: argv.production,
};

var destination = {
    css: 'flamenco/static/assets/css',
    pug: 'flamenco/templates',
    js: 'flamenco/static/assets/js/generated',
}


/* CSS */
gulp.task('styles', function() {
    gulp.src('src/styles/**/*.sass')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(gulpif(enabled.maps, sourcemaps.init()))
        .pipe(sass({
            outputStyle: 'compressed'}
            ))
        .pipe(autoprefixer("last 3 versions"))
        .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
        .pipe(gulp.dest(destination.css))
        .pipe(gulpif(enabled.liveReload, livereload()));
});


/* Templates - Pug */
gulp.task('templates', function() {
    gulp.src('src/templates/**/*.pug')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(cache('templating'))
        .pipe(pug({
            pretty: enabled.prettyPug
        }))
        .pipe(gulp.dest(destination.pug))
        .pipe(gulpif(enabled.liveReload, livereload()));
});


/* Individual Uglified Scripts */
gulp.task('scripts', function() {
    gulp.src('src/scripts/*.js')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(cache('scripting'))
        .pipe(gulpif(enabled.maps, sourcemaps.init()))
        .pipe(gulpif(enabled.uglify, uglify()))
        .pipe(rename({suffix: '.min'}))
        .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
        .pipe(gulpif(enabled.chmod, chmod(0o644)))
        .pipe(gulp.dest(destination.js))
        .pipe(gulpif(enabled.liveReload, livereload()));
});

function browserify_base(entry) {
    let pathSplited = path.dirname(entry).split(path.sep);
    let moduleName = pathSplited[pathSplited.length - 1];
    return browserify({
        entries: [entry],
        standalone: 'flamenco.' + moduleName,
    })
    .transform(babelify, { "presets": ["@babel/preset-env"] })
    .bundle()
    .pipe(gulpif(enabled.failCheck, plumber()))
    .pipe(sourceStream(path.basename(entry)))
    .pipe(buffer())
    .pipe(rename({
        basename: moduleName,
        extname: '.min.js'
    }));
}

function browserify_common() {
    return glob.sync('src/scripts/js/es6/common/**/init.js').map(browserify_base);
}

gulp.task('scripts_browserify', function(done) {
    glob('src/scripts/js/es6/individual/**/init.js', function(err, files) {
        if(err) done(err);

        var tasks = files.map(function(entry) {
            return browserify_base(entry)
            .pipe(gulpif(enabled.maps, sourcemaps.init()))
            .pipe(gulpif(enabled.uglify, uglify()))
            .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
            .pipe(gulp.dest(destination.js));
        });

        es.merge(tasks).on('end', done);
    })
});

/* Collection of scripts in src/scripts/tutti/ to merge into tutti.min.js */
/* Since it's always loaded, it's only for functions that we want site-wide */
gulp.task('scripts_tutti', function(done) {
	let toUglify = ['src/scripts/tutti/**/*.js']

	es.merge(gulp.src(toUglify), ...browserify_common())
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(gulpif(enabled.maps, sourcemaps.init()))
        .pipe(concat("tutti.min.js"))
        .pipe(gulpif(enabled.uglify, uglify()))
        .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
        .pipe(gulpif(enabled.chmod, chmod(0o644)))
        .pipe(gulp.dest(destination.js))
        .pipe(gulpif(enabled.liveReload, livereload()));
    done();
});

/* Simply copy these vendor scripts from node_modules. */
gulp.task('scripts_copy_vendor', function(done) {
    let toCopy = [
        'node_modules/d3/build/d3.min.js',
        'node_modules/d3/build/d3.js',
        'node_modules/dagre-d3/dist/dagre-d3.min.js',
    ];

    gulp.src(toCopy)
        .pipe(gulp.dest(destination.js + '/vendor/'));
    done();
});


// While developing, run 'gulp watch'
gulp.task('watch',function(done) {
    // Only listen for live reloads if ran with --livereload
    if (argv.livereload){
        livereload.listen();
    }

    gulp.watch('src/styles/**/*.sass',['styles']);
    gulp.watch('src/templates/**/*.pug',['templates']);
    gulp.watch('src/scripts/*.js',['scripts']);
    gulp.watch('src/scripts/tutti/*.js',['scripts_tutti']);
    gulp.watch('src/scripts/js/**/*.js', ['scripts_browserify', 'scripts_tutti']);
    done();
});

// Erases all generated files in output directories.
gulp.task('cleanup', function() {
    var paths = [];
    for (attr in destination) {
        paths.push(destination[attr]);
    }

    git.clean({ args: '-f -X ' + paths.join(' ') }, function (err) {
        if(err) throw err;
    });

});

// Run 'gulp' to build everything at once
var tasks = [];
if (enabled.cleanup) tasks.push('cleanup');
gulp.task('default', tasks.concat([
    'styles',
    'templates',
    'scripts',
    'scripts_tutti',
    'scripts_copy_vendor',
]));
